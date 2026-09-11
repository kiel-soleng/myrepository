> **Local enrichment** — 2026-09-11, added after building the UCSC Institutional
> Analytics workbook. Empirically verified against `api.staging.sigmacomputing.io`
> (papercranestaging org) by bisecting POST 400s against a disposable test
> workbook. This supplements (does not replace) `specification/schema.md` and
> `specification/layout.md`, which describe an older schema version. If a spec
> that matches those two files fails with `Invalid kind: "<kind>"` or a masked
> 500, check here first.

# Schema drift — 2026-08+ workbook-spec envelope (verified live)

## 1. The `document{}` envelope replaces the flat top level

`schema.md` documents:

```json
{"name": "...", "folderId": "...", "schemaVersion": 1, "pages": [{"id","name","elements":[...]}], "layout": "..."}
```

The live API on this org instead requires:

```json
{
  "name": "...",
  "folderId": "...",
  "document": {
    "schemaVersion": 1,
    "kind": "workbook",
    "elements": [ /* FLAT — every element from every page, in one array */ ],
    "pages": [ {"id": "pg1", "name": "Overview"} ],
    "settings": {"theme": {"overrides": { "colors": {...}, "categoricalScheme": [...], "borderRadius": "round", "space": {"unit": "small"} }}},
    "layout": "<?xml ...?>..."
  }
}
```

`document.pages[].elements` is **not supported** — page membership comes only
from which `<Page id="...">` block in the layout XML contains the element's
`<Element elementId="...">` tag. `document.pages[]` entries are just `{id, name}`
(+ optional `visibility`).

Endpoints unchanged: `POST /v2/workbooks/spec`, `PUT /v2/workbooks/{id}/spec`,
`GET /v2/workbooks/{id}/spec`, `POST /v2/workbooks/spec/verify`.

**`document.settings.theme.overrides.colors` + `categoricalScheme` ARE
spec-able** — contradicts the "Theme is UI-only" note in `layout.md`. Set brand
colors here instead of telling the user it's a manual step. Font family is
still not in this block (still genuinely UI-only, confirmed by omission).

## 2. Layout XML tags renamed

| Old (schema.md / layout.md) | Current |
|---|---|
| `<LayoutElement>` | `<Element>` |
| `<GridContainer>` | `<Container>` |

Using the old tag names does not produce a validation error — it can return a
masked 500 (`"An error has occurred..."`) or otherwise silently fail to render.
Always use `<Element>` / `<Container>`.

## 3. Field-level changes that cause `Invalid kind: "<kind>"`

Per the hard-won-gotchas pattern: this message almost always means a required
field is missing/wrong-shaped for that kind, not that the kind itself is
unsupported. Verified fixes:

- **`image`** needs `"source": {"kind": "url", "url": "https://..."}` — a bare
  top-level `"url"` field (as `others.md` documents) is rejected.
- **`donut-chart` / `pie-chart`** `value` and `color` take `{"columnId": "<id>"}`,
  not `{"id": "<id>"}` (as `charts.md` documents). `color.sort` and
  `color.scheme` still work alongside `columnId`.
- **`text`** rejects the `verticalAlign` field outright in this version — any
  value (`start`/`middle`/`end`) causes `Invalid kind: "text"`. Omit the field
  entirely; there's no code-rep vertical-align control right now on this org.
- **`conditionalFormats` (`backgroundScale`)** rejects a `domain` field —
  `{"type": "backgroundScale", "columnIds": [...], "scheme": [...]}` works;
  adding `"domain": [...]` (as `tables.md` shows) causes `Invalid kind: "table"`
  on the whole element. Omit `domain`; Sigma auto-scales to the data's min/max.
  `single` and `dataBars` conditional formats were verified unaffected.

Everything else tested this session round-tripped exactly as `charts.md` /
`kpis.md` / `controls.md` / `containers.md` document: `kpi-chart` `value.columnId`,
list controls, `combo-chart` mixed `yAxis.columnIds` (string + `{columnId,type}`),
single-color `color: {by: "single", value: "#hex"}` on bar charts, `top-n`
element filters, plain containers, and `sql`-source tables with
`[Custom SQL/<col>]` formula prefixes.

## 3a. `input-table` column shape and `source.kind: "empty"`

`tables.md` documents `input-table` columns as `{id, name, columnType}`. On
this org, the accepted field is **`type`, not `columnType`** —
`{"id": "sv-name", "type": "text", "name": "Scenario Name"}`. Sending
`columnType` produces the generic `Invalid kind: "input-table"` (no hint
that the field name is wrong).

`source: {"kind": "empty"}` alone is also rejected — an **empty source needs
a `connectionId`** even though there's no explicit warehouse table backing
it yet: `"source": {"kind": "empty", "connectionId": "<snowflake-conn-uuid>"}`.
Found by reading a real `input-table` element off an existing workbook's
GET-spec (`kind: "table"` sources need a `connectionId` too, so this isn't
surprising in hindsight, but neither `tables.md` nor the OpenAPI-derived
docs mention it for the `empty` variant specifically).

Once the shape is right, `input-table` elements work as genuine write-back
with **zero extra plumbing**: each row a user adds via Sigma's native
input-table "+ add row" UI is a real persisted row, immediately queryable
by other elements on the page — no `button` + `insert-rows` action needed
for the basic "let users create new records" capability. Save that
combination for cases that need a specific trigger/workflow (approve,
submit, reset), not for basic row creation.

## 3b. Bare control-value references work for `list`, not just `segmented`

`controls.md`'s "Numeric parameter control referenced from formulas" section
demonstrates bare `[ControlId]` formula references only for `segmented`
controls. Verified this session: the same bare-reference mechanism works
identically for a **`list`** control with `selectionMode: "single"` — its
currently-selected value (a text string here) is readable from any formula
on the page via `[<controlId>]`, exactly like `segmented`. Useful for
"pick a saved record, look up its values" patterns:

```
{"id": "active-key", "name": "Active Scenario Key", "formula": "[ActiveScenario]"}
...
"formula": "Lookup([Saved Scenarios/Growth %], [Active Scenario Key], [Saved Scenarios/Scenario Name])"
```

This composes with `Lookup()` (see `formulas.md`) to pull a value out of an
`input-table` keyed by whatever the user currently has selected in a list
control — a lightweight alternative to wiring an actual filter/join when
you just need one scalar per row, broadcast from a control's selection.

## 4. `scripts/validate-spec.py` does not understand this envelope

The repo's own pre-POST validator (`_all_elements()`, `issues_elements_placed()`,
etc.) reads `spec.get("pages", [])` then `p.get("elements", [])` per page — the
OLD shape. Against the new `document{}` envelope, every page's `.get("elements")`
returns `[]`, so the validator finds **zero elements** and reports
`"all 13 checks passed"` even when the spec is structurally broken and will 400
on POST. **Do not treat a clean `validate-spec.py` run as evidence a
document-enveloped spec is POST-able.** POST (create) is the real check; `/spec/verify`
is weaker still (structure-only, doesn't resolve SQL or catch dangling refs).

This validator has not yet been updated for the new envelope — that's a
follow-up, not done as part of this note.

## Source

Cross-checked against `millersigma/skills/sigma-workbook-conventions/reference/schema-2026-08-breaking-changes.md`
on the `claude/clone-millersigma-repo-vbkdqa` branch of this repo (a separate,
more extensive writeup from a prior build on this same org, covering overlays,
agents, action effects, and reports-as-code — not reproduced in full here since
this workbook didn't need those surfaces). Read that file directly if a future
build needs modals, drawers, agents, or report code-rep.
