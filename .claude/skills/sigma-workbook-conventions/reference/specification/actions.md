# Buttons, actions, and overlays (modals/drawers)

Verified 2026-09-10 building a UCSC budget-planning app with a writeback
grid, approval workflow, and a request-form modal. Confirmed both by
direct probing against a live tenant and by GET-spec on real harvested
production workbooks (SoFi, Casa, Risepoint builds) — this is the first
time this skill documents these element kinds; `reference/specification/tables.md`
→ "Input tables" previously said actions weren't available yet. They are.

## `button` element

```json
{
  "id": "btn-submit-plan",
  "kind": "button",
  "text": "Submit Plan",
  "appearance": "filled",
  "style": { "backgroundColor": "#003c6c", "borderRadius": "round" },
  "actions": [
    {
      "id": "a-submit-plan",
      "trigger": "on-click",
      "effects": [ { "...": "one or more effect objects, see below" } ],
      "successToast": { "title": "Plan submitted", "showMessage": "shown" }
    }
  ]
}
```

- **Label field is `text`, not `name`.** Every other element kind in
  this skill uses `name` for its display label — buttons are the
  exception.
- `appearance`: `"filled"` | `"text"` | `"outline"` (observed on real
  workbooks).
- `actions` is an array of trigger blocks. Each has `id`, `trigger`
  (`"on-click"` for buttons), an `effects` array (fires in order), and
  an optional `successToast: {title, showMessage: "shown"}`.
- Multiple effects fire in sequence on one trigger — e.g. `insert-rows`
  then `close-overlay`, or `set-control-value` then `open-overlay`.

## Action effects

All effects that reference a table use **`tableElementId`** as the key
— NOT `table`. (An external/upstream reference doc claims `table`; that
doc is wrong on this specific field name. Verified against 3 independent
real harvested workbooks, all using `tableElementId`. Trust a real
GET-spec example over any written reference, including this file, if
they ever disagree again.)

### `update-rows`

```json
{ "effect": "update-rows", "tableElementId": "it-budget-plan",
  "whichRows": { "type": "formula", "formula": "[Department] = [DeptPlanDept] And [Approval Status] = \"Draft\"" },
  "values": { "bp-status": { "type": "constant", "value": { "type": "text", "value": "Submitted" } } } }
```

- `whichRows`: `{ "type": "formula", "formula": "<boolean Sigma formula>" }`
  is the common case — `"True"` means "all rows." The formula can bare-
  reference page controls (`[DeptPlanDept]`) alongside the table's own
  column names (`[Department]`) — confirmed working for `list`-type
  single-select controls, not just `segmented` manual-value controls
  (see `controls.md` → "Numeric parameter control referenced from
  formulas" for the segmented case this generalizes from).
- `values`: a map of `<column-id>: <value-spec>`. Value-spec forms:
  - `{ "type": "constant", "value": { "type": "text"|"number"|"boolean"|"date", "value": <literal> } }`
  - `{ "type": "control", "control": "<controlId>" }`
  - `{ "type": "formula", "formula": "<Sigma formula>" }`
  - `{ "type": "column", "column": "<column-id>" }`
  - `{ "type": "agent-input", "inputName": "<name>" }` (for agent-tool actions)

### `insert-rows`

```json
{ "effect": "insert-rows", "tableElementId": "it-reallocation",
  "values": {
    "rr-department": { "type": "control", "control": "ReallocDept" },
    "rr-status": { "type": "constant", "value": { "type": "text", "value": "Pending" } }
  } }
```

Same `values` shape as `update-rows`. No `whichRows` — it always
appends one new row.

### `delete-rows`

```json
{ "effect": "delete-rows", "tableElementId": "it-cohorts",
  "whichRows": { "type": "formula", "formula": "True" } }
```

Same `whichRows` shape as `update-rows`. **Linked input-tables (backed
by a real warehouse table) cannot `delete-rows`** — their rows come from
the source; reset by `update-rows`-ing the editable columns to null
instead (per the external millersigma reference doc — not independently
re-verified here, but consistent with how `kind: "empty"` vs `"linked"`
input-tables differ).

### `set-control-value` / `clear-control`

```json
{ "effect": "set-control-value", "control": "cardProduct",
  "value": { "type": "constant", "value": { "type": "text", "value": "Residential Rent Payments" } } }
```

```json
{ "effect": "clear-control", "scope": { "type": "control", "controlId": "CohortName" } }
```

**Note the asymmetry:** `set-control-value` takes the control's id under
the key `control`; `clear-control` nests it one level deeper as
`scope: { type: "control", controlId: ... }` — `controlId`, not
`control`, inside `scope`. Easy to typo.

### `open-overlay` / `close-overlay`

```json
{ "effect": "open-overlay", "overlayId": "modalReallocation" }
{ "effect": "close-overlay", "overlayId": "modalReallocation" }
```

`overlayId` matches an entry in `document.overlays` (see below).

### Others (documented by the external millersigma reference, not yet
independently re-verified in this skill's own corpus)

`open-url`, `refresh-element`, `navigate` (`{effect: "navigate", target: {type: "page", page: "<page-id>"}}`),
`select-tab`, `open-document` (cross-document, can target a report),
`sequence` (runs a named sequence of steps). Treat these as probably-
correct but verify against a real POST before relying on them.

## Overlays — modals and drawers

Top-level `document.overlays` array, sibling to `pages`/`elements`:

```json
"overlays": [
  {
    "id": "modalReallocation",
    "type": "modal",
    "name": "Request Reallocation",
    "modal": {
      "width": "small",
      "header": { "title": "Request a budget reallocation", "showCloseIcon": "shown" },
      "footer": { "primaryCta": { "visible": "hidden" }, "secondaryCta": { "visible": "hidden" } }
    }
  }
]
```

- `type`: `"modal"` | `"drawer"`. A drawer uses a `drawer` key instead of
  `modal`, with `width`, `header`, `position` (`"start"`|`"end"`),
  `showShadow`.
- `modal.width` / `drawer.width`: `"x-small"` | `"small"` | `"medium"` |
  `"large"` | `"x-large"`.
- The footer CTAs are usually hidden (`visible: "hidden"`) when the
  modal's own body has its own buttons (the common pattern — see
  layout below).

### Overlay content lives in its own `<Page>` in the layout XML

An overlay's content elements are placed exactly like a normal page —
**the overlay's `id` doubles as a `<Page id="...">` id** in the layout
XML, populated with ordinary `<Element>`/`<Container>` tags:

```xml
<Page type="grid" gridTemplateColumns="repeat(12, 1fr)" gridTemplateRows="auto" id="modalReallocation">
  <Element elementId="m-realloc-title" gridColumn="1 / 13" gridRow="1 / 3"/>
  <Element elementId="ctrl-realloc-from" gridColumn="1 / 7" gridRow="5 / 7"/>
  <Element elementId="btn-realloc-submit" gridColumn="6 / 13" gridRow="13 / 15"/>
</Page>
```

Modals commonly use a narrower grid (e.g. `repeat(12, 1fr)`) than the
main 24-column page grid, but 24 works too. The elements referenced
inside (text, controls, buttons) are ordinary elements in
`document.elements` — same as any page's content, just placed under the
overlay's page block instead of a real page's.

### `list` control `values` defaults don't reliably round-trip — guard formulas with `IsNull`

> ⚠️ **2026-09-10.** A single-select `list` control authored with an
> initial `values: ["FY2027"]` came back as `values: null` on GET-spec.
> This is the same class of gap `controls.md` already documents for
> `number-range` (`values` doesn't reliably round-trip) — now also seen
> on `list`. Any KPI/chart formula that bare-references that control
> inside a `SumIf`/`If` (e.g. `[Budget Detail/Fiscal Year] =
> [DeptPlanFY]`) then compares against an unset value and silently
> returns 0/blank the moment the user hasn't touched the control yet —
> which looks exactly like "this tab has no data."
>
> **Don't rely on a control default for anything formula-critical.**
> Guard every such reference with a literal fallback instead:
>
> ```
> SumIf([Budget Detail/Proposed Amount],
>       [Budget Detail/Fiscal Year] = If(IsNull([DeptPlanFY]), "FY2027", [DeptPlanFY]))
> ```
>
> This makes the KPI show a sensible number on first load regardless of
> whether the control's authored default actually stuck — cheap
> insurance, and it degrades gracefully instead of silently blanking.

### Text-entry controls with no filter target

A control used purely to collect a value for an `insert-rows`/
`update-rows` action (not to filter any table) can omit `filters`
entirely — confirmed working for `controlType: "text"` and `"text-area"`
with no `filters` array at all:

```json
{ "kind": "control", "id": "ctrl-realloc-justification", "controlId": "ReallocJustification",
  "name": "Justification", "controlType": "text-area", "mode": "equals", "value": "", "case": "insensitive" }
```

This generalizes the pattern `controls.md` → "Numeric parameter control
referenced from formulas" already documents for `segmented` controls —
`filters` is only required when the control is meant to filter a target
element's rows, not when it's just a value source for formulas/actions.

## Cross-references

- `reference/specification/tables.md` → "Input tables" for the
  `input-table` element shape these actions read/write.
- `reference/specification/controls.md` for control shapes referenced
  by `{type: "control", control: "..."}` value specs.
- `reference/history.md` → "2026-09-10" for the full incident.
