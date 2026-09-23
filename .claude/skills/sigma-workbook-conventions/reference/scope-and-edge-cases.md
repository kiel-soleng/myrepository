# Scope and edge cases

What the workbooks-as-code feature does NOT represent, the misleading
errors and 500s observed on this org, and the fallback rituals. Load when
something fails unexpectedly or before relying on a feature you haven't
round-tripped before.

This file is the **ryan-specific edge-case log**. For canonical per-element
shapes see `reference/specification/`; for the validation flow see
`reference/workflows/validate.md`. The schema-drift and persist-spec
rituals previously here have moved to `reference/workflows/crud.md`.

## Table of contents

- [Scope of the code representation](#scope-of-the-code-representation)
- [GET-spec can 500 when UI features aren't representable](#get-spec-500)
- [POST/PUT can't construct what GET-spec serializes](#post-put-cant-construct)
- [Map element status](#map-element-status)
- [Falling back to `warehouse-table` source](#falling-back-to-warehouse-table-source)

---

## Scope of the code representation

The workbooks-as-code feature is **not a fully scoped definition of a Sigma
workbook**. Some element properties configurable in the UI are not
addressable in the spec, and a GET-back of a UI-configured workbook will
not necessarily round-trip every visual setting. Known examples (treat as
limitations, not bugs to fix):

- **KPI period-comparison configuration** (e.g. "vs prior month" vs "vs
  prior quarter"): the spec only carries the date-dimension column on the
  KPI's `columns` array. The actual comparison period Sigma renders from
  that column is UI-side state and isn't surfaced in the GET response. If
  a user needs a specific comparison period, configure it in the UI;
  don't try to set it in the spec. **Narrowed 2026-05-19:** KPI title
  color, font size, weight, and the element frame (border) ARE spec-able
  via the styled-name object and the `style` field — see
  `reference/specification/kpis.md` → "Title styling." Only the
  comparison-period and sparkline-toggle remain UI-only on KPIs.

- **Chart series colors** beyond the `color.scheme` palette:
  per-chart-spec `color: {by, column, scheme}` lets you set positional
  palettes (`category` mode) and continuous gradients (`scale` mode) —
  see `reference/specification/charts.md`. But the **fallback / theme
  palette** when `color` is unset comes from Administration → Branding
  Settings → Workbook Themes, applied via Workbook Settings → Theme.
  To rebrand the default chart colors org-wide, edit the workbook theme.

- **Chart axis label rotation:** Sigma auto-rotates labels that would
  overlap; no spec override. For bar charts with categorical x-axis, use
  `orientation: "horizontal"` (see
  `reference/conventions.md` → "Bar-chart orientation"). For time-series,
  widen the chart.

- **Padding / spacing / gap on containers and layouts** — verified
  2026-05-21 against the retail-sales harvest. Design specs mention
  `padding`, `ContainerSpacing`, `gap` but none survive into the JSON or
  layout XML on GET-back. UI-only.

- **Modal / popover pages, tabbed containers, buttons, action sequences**
  — per Sigma's official workbooks-as-code limitations, these are NOT
  supported in the spec. Workbooks that use them render in the UI but
  break GET-spec — see "GET-spec can 500" below. When the user asks for
  one, surface during planning and propose a substitute (drill-through
  actions, separate pages, etc.).

(Add new findings here when you discover other UI-only properties.)

The practical implication for the iteration loop: when a user UI-fix
changes something visible but the diff against the prior spec is empty,
that property lives outside the code representation. Note it here and
move on — don't burn iterations searching for a field that doesn't exist.

## GET-spec 500

The GET-spec endpoint can return HTTP 500 (`code: service_error`) on a
workbook that's otherwise healthy — open-able in the UI, listed in
`/v2/files`, metadata fetchable via `GET /v2/workbooks/{id}`.

**Confirmed trigger:** pivot-table cell-color conditional formatting
(heatmap visual). Reproducible via UI toggle:

| Workbook state | GET-spec |
|---|---|
| Conditional formatting applied | 500 (`service_error`) |
| Conditional formatting removed via UI | 200 |
| Conditional formatting re-applied | 500 |
| Unrelated control workbook | 200 throughout |

> **2026-05-21 update.** The upstream `sigma-workbooks` skill claims
> `conditionalFormats` round-trips cleanly. If true on the current
> platform, the trigger above may be **stale**. The four workbooks the
> user supplied during the 2026-05-21 training session that returned
> `service_error` (Claims Command Center, Sales MBR original + stripped
> twice, Healthcare Aesthetic) likely tripped on different features —
> the Healthcare summary explicitly mentions maps, buttons, modals.
> Retest required before relying on either claim. Stage 7 of the
> migration will probe these workbooks again.

Suspected triggers (untested):

- Buttons / modal pages / tabbed containers (per Sigma's documented
  unsupported list)
- Possibly chart series breakout / color-by combined with conditional
  formatting

Maps used to be on this list but were verified round-trippable
2026-07-02 — see "Map element status" below.

**Cross-workbook scope:** rollback-by-version-param doesn't help.
Verified 2026-05-21 against Sales MBR stripped — all 4 versions
returned `service_error`. Once a workbook trips this failure mode, it
appears to stay tripped across versions.

Diagnostic steps when GET-spec returns 500:

1. **Sanity check** another workbook's GET-spec to rule out a global
   serializer outage. `scripts/api/whoami.sh` exercises this on the
   `/v2/files` listing.
2. **Capture the `incident-id`** from the response body and file a
   Sigma support ticket — this is a server-side bug.
3. **Isolate the trigger via UI undo.** Undo one UI change at a time,
   save, retry GET-spec. If 200, that change is the culprit.
4. **Don't try to repair via PUT** — overwriting with a known-good
   spec would destroy the new UI configuration.

Practical rule: configure suspected-trigger features (pivot cell
heatmaps, maps, buttons) **last**, after any spec round-tripping for
that workbook is done. Once they're applied, GET-spec may be dead for
that workbook until they're removed.

`scripts/api/harvest-workbook.sh` fails fast on `service_error`
responses with a diagnostic message — added 2026-05-21 after four
workbook harvests all tripped this.

## POST/PUT can't construct

The asymmetry above (`GET-spec 500`) is GET-side: a workbook that renders
fine in the UI can break the *read* path. This section is the opposite
direction: layout constructs that GET-spec serializes without complaint,
but that `POST /v2/workbooks/spec` and `PUT .../spec` can never build from
scratch — the CREATE-time validator either rejects them outright or, worse,
fails with a cryptic error that doesn't name the actual cause. Both
confirmed cases below were found by harvesting a real, UI-built workbook
and re-POSTing its own GET-spec output unmodified — that alone is enough
to reproduce.

### `type="stack"` layout containers

A `<Container type="stack" ...>` in the layout XML is how the UI
represents a couple of stacked/overlapping elements (e.g. a KPI tile with
an icon layered on top). GET-spec always serializes these as **empty stub
containers** — it never emits the nested `<Element>` children that must
logically exist inside them.

Nesting `<Element>` tags inside the stub yourself does **not** fix it —
confirmed via an isolated test with every other validator error category
pre-fixed: the elements still come back `"element '<id>' is not placed in
layout"`. Sigma's placement validator runs last in its error-category
order (comparison configs → sort refs → waterfall shape → modal actions →
agent dataSources → placement), so this error can be masked by earlier,
unrelated errors during iterative fixing — don't conclude a stack fix
"almost worked" just because a *different* error appeared next; re-test
the stack fix in isolation once everything else is clean.

**No fix exists.** The only working path found so far: drop the elements
living inside `type="stack"` containers from the spec (they're typically
decorative — icon overlays, badge stacking — not load-bearing data
elements). Surface this to the user before dropping anything; don't
silently remove elements that turn out to carry data or actions.

### The workbook-level header `panels[]` construct

Some workbooks have a shared, cross-page header (logo, a duplicate
page-nav bar, decorative icons, a divider) defined via the top-level
`panels[]` array plus a matching `<Panel id="...">` block in the layout
XML — a sibling of the `<Page>` blocks, not nested inside one.

GET-spec serializes this correctly. **Any spec containing a `<Panel>`
layout block fails POST/PUT** with:

```
Layout parent not found in getLayoutParentByLayoutIdOrFail
```

This error gives no field path and no hint that a Panel is involved — it
looks like a generic layout-tree bug. It's easy to misdiagnose as a
page/overlay count limit if you're bisecting by dropping whole pages —
any bisection harness that strips unrecognized top-level layout blocks
(anything whose `id` isn't in the kept-pages set) will silently drop the
Panel along with whatever page/overlay it's actually testing, making
*every* reduced test "pass" regardless of the real culprit. Isolate the
Panel by itself — one trivial page, zero overlays, Panel present — to
confirm it's the Panel and not a count effect.

**Fix:** duplicate the Panel's children onto each *visible* page as
ordinary page-scoped elements (fresh element ids, cloned JSON defs, fresh
action ids too — `"Duplicate layout element id"` / `"Duplicate action
id"` are both enforced), then drop `panels: []` and the `<Panel>` layout
block. Skip hidden pages — they never render in the tab bar, so a header
there is wasted elements. Shift every pre-existing top-level child's
`gridRow` on that page down by the header's row-span so the two don't
overlap (only direct children of the `<Page>` node — nested descendants
are relative to their own parent's coordinate system, not the page's).
Sigma's native page-tab bar is independent of this custom Panel, so
page-to-page navigation is unaffected either way; only the custom nav
bar/logo/icons are lost if you don't clone them.

Confirmed working end-to-end (2026-09-23): a 7-page, 10-overlay, 282-element
workbook with the header duplicated across 5 visible pages POSTs and PUTs
cleanly with `verify-workbook.sh` reporting all elements compile.

## Map element status

**Supported.** Verified 2026-07-02: three map element kinds
(`geography-map`, `point-map`, `region-map`) round-trip cleanly through
POST/GET on this org. Harvest of `Element-Showcase-Dashboard`
(`6DGOTggv4x90Cls7Sq0y0j`) included both a `region-map` (us-state) and
a `point-map` (bubble by margin), both readable back cleanly.

See `reference/specification/maps.md` for the full shape guide,
including the `regionType` enum for `region-map` and the single-vs-
array shape gotcha on binding fields.

Historical note: prior to the 2026-07-02 validation, every
map-bearing workbook observed on this org returned `service_error` on
GET-spec. That's no longer the case — the earlier failures were
against workbooks that combined maps with a different unsupported
feature (likely pivot cell heatmaps or an unsupported control kind).
Author maps freely; only surface a scope caveat if the user's other
requested features overlap the known-failing feature list above.

## Falling back to `warehouse-table` source

When a `data-model`-sourced spec fails at POST and the data-model
element isn't load-bearing for the workbook's analytical question,
fall back to sourcing directly from the underlying warehouse table.

The data model's value is its joins + metrics + column-level security.
If your workbook needs none of those (a single-table dashboard with
hand-derived calcs), `warehouse-table` source is simpler and
sometimes unblocks builds when the DM has issues.

Discovery flow: `scripts/api/lookup-path.sh <conn-id>
"<DB>.<SCHEMA>.<TABLE>"` resolves the inodeId; then
`scripts/api/list-table-columns.sh <inode-id>` lists columns. Switch
the spec's source from `kind: "data-model"` to `kind: "warehouse-
table"` and update all column formulas from `[<DM-element-name>/Col]`
to `[<TABLE>/Col]`.

`scripts/sigma-resolve.py` handles the resolution when the prompt
mixes warehouse paths and folder names. See
`reference/workflows/discover.md`.

## History reference

Dated incident notes (per-page layout discarded, cohort groupings
shape, DivideSafe hallucination, format-field discovery, styled-name
discovery, the 2026-05-21 migration, etc.) live in
`reference/history.md`. Inline rules in this and other chunks are
evergreen; the history file carries **when** each rule was verified
and the incident that surfaced it.
