# Tables

The `table`, `pivot-table`, and `input-table` element kinds.

```bash
jq '.components.schemas.Table, .components.schemas.PivotTable, .components.schemas.InputTable' /tmp/sigma-api.json
```

The `table` element is the most common element kind and the primary way
data enters a workbook — charts, KPIs, and other elements usually point
their `source` at a table.

## Table of contents

Table element:

- [Basic shape](#basic-shape)
- [Styled `name` + `description` + `noDataText`](#styled-name--description--nodatatext)
- [Common optional fields](#common-optional-fields):
  - [`order`](#order)
  - [`groupings` — multi-level aggregation](#groupings--multi-level-aggregation)
  - [`summary` — summary-bar pattern](#summary--summary-bar-pattern)
  - [`filters` — top-N, element-level row filters](#filters--top-n-element-level-row-filters)
  - [`visibleAsSource`](#visibleassource)
  - [`folders` — column folder groupings](#folders--column-folder-groupings)
  - [`tableStyle` — banding + presets + header styling](#tablestyle--banding--presets--header-styling)
  - [`tableComponents` — collapsed columns](#tablecomponents--collapsed-columns)
- [Conditional formatting — `conditionalFormats`](#conditional-formatting--conditionalformats) (single, backgroundScale, fontScale, dataBars)

Pivot tables:

- [Shape](#shape)
- [Round-trip quirks](#round-trip-quirks)
- [Pivot conditional formatting — status](#pivot-conditional-formatting--status)
- [Cohort pivot pattern](#cohort-pivot-pattern)

Input tables:

- [Input tables](#input-tables) (minimal — value limited until actions land)

- [Cross-references](#cross-references)

---

## Basic shape

```json
{
  "id": "sales-table",
  "kind": "table",
  "name": "Sales Data",
  "source": {
    "kind": "warehouse-table",
    "connectionId": "<conn-uuid>",
    "path": ["DATABASE", "SCHEMA", "TABLE"]
  },
  "columns": [
    { "id": "col-1", "name": "Column Name", "formula": "[TABLE/column_name]" },
    { "id": "col-2", "name": "Total", "formula": "Sum([Column Name])" }
  ],
  "order": ["col-1", "col-2"]
}
```

See `sources.md` for all source kinds and `formulas.md` for
column-reference rules. Every column needs `id`, `name`, `formula`;
optional `format` (see `formatting.md`).

## Styled `name` + `description` + `noDataText`

`name` accepts either a plain string OR a styled object for headers
— same shape as KPI / chart titles:

```json
"name": {
  "text": "Sales Data",
  "fontSize": 18,
  "fontWeight": "bold"
}
```

Tables also accept optional `description` and `noDataText`:

```json
"description": {
  "text": "Latest quarter"
},
"noDataText": "No rows in range"
```

The shape mirrors chart titles; fetch `TitleSection` from the
OpenAPI for the full styling enum.

**`description` must be an object on tables (and KPIs).** POST
rejects a plain-string `description` with `Invalid object: string`.
Even if you just want a plain caption, wrap it:

```json
"description": { "text": "Distinct SKUs with < 100 units sold" }
```

To hide the description entirely:

```json
"description": { "visibility": "hidden" }
```

Verified 2026-07-02 against `inventory-health` build (1 POST retry).

## Common optional fields

### `order`

Array of column IDs controlling left-to-right display order.
Defaults to declaration order.

### `groupings` — multi-level aggregation

Creates a hierarchical / pivot view without changing element kind.
Each entry is one **level** in the hierarchy:

```json
"groupings": [
  {
    "id": "by-region",
    "groupBy": ["col-region"],
    "calculations": ["col-total", "col-profit"]
  },
  {
    "id": "by-product",
    "groupBy": ["col-product-line"],
    "calculations": ["col-line-rev", "col-pct-of-total"]
  }
]
```

The shape `{id, groupBy: [<col-id>], calculations: [<col-id>]}` is
canonical. Legacy `{id, columnId}` and `{id}`-only forms are
render-hint serializations from older GET-backs — they don't
aggregate. Use the canonical shape for any new authoring. See
`reference/history.md` → "2026-05-13 — Cohort iteration."

Multi-level groupings produce real `GROUP BY` SQL — one per level,
joined so each detail row carries the aggregates from its ancestor
levels. Canonical example:
`examples/data-model-sourced-multi-level-aggregated-table.json`.

### `summary` — summary-bar pattern

A top-level field on the table element (singular `summary`, NOT
`summaries`). Each entry is a column id whose formula is evaluated
at the summary-bar grain (across all rows of the table). The
summary value is broadcast to every row.

```json
"summary": ["col-median-margin"]
```

Use cases: median/mean/percentile thresholds for downstream
bucketing columns. Full pattern + rationale in
`reference/conventions.md` → "Summary-bar pattern."

**`summary` × `groupings.calculations` are mutually exclusive.** A
column id in `summary` MUST NOT also appear in any grouping's
`calculations` list. POST rejects with
`Duplicate column or folder reference: '<col-id>'`. Verified
2026-07-02 against `exec-scorecard` v1 (blocked mid-build).

If you need both the summary-bar view AND the per-group aggregation,
define **two separate columns** with distinct ids and the same
formula. Put one in `summary`, the other in `calculations`.

### `filters` — top-N, element-level row filters

```json
"filters": [
  {
    "id": "top-20",
    "columnId": "col-revenue",
    "kind": "top-n",
    "rankingFunction": "rank",
    "mode": "top-n",
    "rowCount": 20,
    "includeNulls": "when-no-value-is-selected"
  }
]
```

> **`rowCount` takes a number literal only** — cannot be parametrized
> by a control. `rowCount: "[TopN]"` is rejected. Control bindings
> apply to filter **values**, not structural fields like `rowCount`,
> `rankingFunction`, `mode`, or `kind`. To vary the cap interactively,
> duplicate the element per cap.

### `visibleAsSource`

Boolean. Whether this table is exposed as a source for other
elements on the page. Defaults to `false` (often) — set explicitly
to `true` for parent tables that downstream KPIs/charts source from.

### `folders` — column folder groupings

```json
"folders": [
  { "id": "store-fields", "name": "Store Fields",
    "items": ["col-store-key", "col-store-name", "col-store-region"] },
  { "id": "customer-fields", "name": "Customer Fields",
    "items": ["col-cust-key", "col-cust-name"] }
]
```

UI-side organization for tables with many columns. Doesn't affect
render or downstream references; just collapses column groups in
the table header.

### `tableStyle` — banding + presets + header styling

Table-level visual styling:

```json
"tableStyle": {
  "banding": "shown",
  "preset": "presentation",
  "cellSpacing": "extra-small",
  "textStyles": {
    "header": { "backgroundColor": "#e2e2e2" }
  }
}
```

| Field | Observed values | Notes |
|---|---|---|
| `banding` | `"shown"` | Row banding on/off |
| `preset` | `"presentation"` | Named style preset |
| `cellSpacing` | `"extra-small"` | d3-style enum |
| `textStyles.header.backgroundColor` | hex color | Header cell background |

Verified 2026-07-02 against `sales-mbr-sentinel`. Full enum values
live in the OpenAPI:

```bash
jq '.components.schemas.TableStyle // .. | select(.properties?.banding? or .properties?.preset?)' /tmp/sigma-api.json
```

### `tableComponents` — collapsed columns

```json
"tableComponents": {
  "collapsedColumns": ["col-order-id", "col-cust-key"]
}
```

`collapsedColumns` names column IDs whose values should render
collapsed by default. UI-side hint; doesn't affect data.

## Conditional formatting — `conditionalFormats`

Threshold-based cell coloring. Verified 2026-05-21 against the
official skill — round-trips through GET unchanged; PUT-based edits
are stable.

```bash
jq '.components.schemas.ConditionalFormatSingle, .components.schemas.ConditionalFormatBackgroundScale, .components.schemas.ConditionalFormatFontScale, .components.schemas.ConditionalFormatDataBars' /tmp/sigma-api.json
```

Four variants: `single` (threshold rules), `backgroundScale`
(gradient scale on cell bg), `fontScale` (gradient on font color),
`dataBars` (inline data bars in the cell).

### `single` — red/green threshold

```json
"conditionalFormats": [
  {
    "type": "single",
    "columnIds": ["col-revenue"],
    "condition": ">",
    "value": 1000,
    "style": { "backgroundColor": "#22c55e" }
  },
  {
    "type": "single",
    "columnIds": ["col-revenue"],
    "condition": "<",
    "value": 100,
    "style": { "backgroundColor": "#ef4444" }
  }
]
```

Condition operators: `=`, `!=`, `>`, `>=`, `<`, `<=`, `IsNull`,
`IsNotNull`, `Contains`, `NotContains`, `StartsWith`, `EndsWith`,
`Between`, `NotBetween`, and `formula` (arbitrary boolean).

Style block supports `backgroundColor`, `color`, `bold`, `italic`,
`underline`, and column-level `format` override.

### `backgroundScale` — heatmap-style gradient

```json
{
  "type": "backgroundScale",
  "columnIds": ["col-revenue"],
  "scheme": ["#fef3c7", "#fbbf24", "#dc2626"],
  "domain": [0, 5000, 10000]
}
```

### `fontScale` — gradient on text color

```json
{
  "type": "fontScale",
  "columnIds": ["col-margin"],
  "scheme": ["#ef4444", "#fbbf24", "#22c55e"]
}
```

### `dataBars` — inline horizontal bars

```json
{
  "type": "dataBars",
  "columnIds": ["col-revenue"],
  "color": "#3b82f6"
}
```

### Round-trip status — verify before relying

> ⚠️ **2026-05-21 update.** The upstream `sigma-workbooks` skill
> claims `conditionalFormats` round-trips cleanly. **This skill's
> earlier observation that pivot cell heatmaps break GET-spec was
> from prior platform behavior.** The retest is part of Stage 7 of
> the migration plan — if confirmed fixed, the warning in
> `scope-and-edge-cases.md` will be amended.
>
> Until confirmed: assume `conditionalFormats` on `table` works (per
> official); on `pivot-table` may still trigger the
> `service_error` 500 on GET-spec — apply LAST after all spec
> round-tripping is done.

---

# Pivot tables

The `pivot-table` element is a sibling of `table` for cross-tab
analysis — measure cells aggregated across one or more row/column
dimensions.

## Shape

Pivots need **three explicit fields** on top of `columns`: `rowsBy`,
`columnsBy`, and `values`. Without `rowsBy` + `columnsBy`, the pivot
collapses to a single grand-total row — no rows or columns render.

```json
{
  "id": "deployments-pivot",
  "kind": "pivot-table",
  "name": "Deployments by cloud and env",
  "source": { "kind": "table", "elementId": "deployments-source" },
  "columns": [
    { "id": "piv-cloud", "name": "Cloud", "formula": "[Deployments/Cloud]" },
    { "id": "piv-env",   "name": "Environment", "formula": "[Deployments/Environment]" },
    { "id": "piv-count", "name": "Deployments",
      "formula": "CountDistinct([Deployments/Deployment UUID])",
      "format": { "kind": "number", "formatString": ",.0f" } }
  ],
  "rowsBy":    [ { "id": "piv-cloud" } ],
  "columnsBy": [ { "id": "piv-env" } ],
  "values":    [ "piv-count" ]
}
```

Field roles:

- **`columns`** — every column referenced by the pivot (dimensions AND
  measures), each with `id`, `name`, `formula`.
- **`rowsBy`** — array of `{ id: <column-id> }` entries. Each entry
  becomes a row-axis dimension. Multiple entries stack (multi-level rows).
- **`columnsBy`** — array of `{ id: <column-id> }` entries. Each becomes
  a column-axis dimension. Multi-level columns work the same way.
- **`values`** — array of column-ID strings. Each is a measure that
  fills the pivot's cells at each (row, column) intersection.

Both `rowsBy` and `columnsBy` entries accept an optional `sort` field:

```json
"rowsBy":    [ { "id": "piv-region", "sort": { "by": "piv-current", "direction": "descending" } } ],
"columnsBy": [ { "id": "piv-quarter", "sort": { "by": "piv-quarter-num", "direction": "ascending" } } ]
```

**Common trap** — including a dimension in `columns` but forgetting
to bind it via `rowsBy` or `columnsBy` renders it as a leaf column on
the source table rather than a pivot axis. The pivot compiles cleanly
(passes validate + verify) but the UI shows only the grand total for
the measure. Verified 2026-07-02 against `Product-and-Basket-Performance`
before a PUT fix added `rowsBy`/`columnsBy` to both pivots.

**Heatmap pattern** (dimension × dimension × measure with cell coloring)
uses this exact shape plus `conditionalFormats` with the
`backgroundScale` variant — see below.

## Round-trip quirks

- **Column reordering.** Sigma reorders the `columns` array on
  round-trip — value columns first, then dimensions — regardless of
  submission order. GET → edit → PUT will show a non-substantive
  diff in `columns`. The `rowsBy` / `columnsBy` / `values` bindings
  preserve IDs, so rendered output is unchanged.

## Pivot conditional formatting — status

Pivot `conditionalFormats` historically broke GET-spec (returns
`service_error` 500). Per the 2026-05-21 official-skill merger, the
upstream skill claims this is fixed. **Retest before relying.**
Apply pivot conditional formatting LAST in the iteration cycle so
that if GET-spec breaks, you don't lose the rest of your work.

## Cohort pivot pattern

For weeks-since-first-action / cohort retention analyses, build a
two-tier source structure and pivot the derived table by cohort
week × age week. Canonical example:
`examples/data-model-sourced-cohort-pivot.json`.

The pivot's columns include both dimensions (cohort dim + age dim)
and aggregated values (`Sum([Revenue])`, `CountDistinct([Cust Key])`).
See `reference/conventions.md` → "Two-tier sourcing."

# Input tables

The `input-table` element is an editable table — users type values
directly into cells, backed by a provisioned warehouse table.

**Status (2026-09-10, verified live):** actions have landed — see
`reference/specification/actions.md` for `button` elements and the
`update-rows`/`insert-rows`/`delete-rows` effects that read/write these
tables. Shape below corrected against real harvested production
workbooks and a live build; the 2026-07-02 shape (`columnType`, no
`connectionId`) was wrong on two fields.

## Shape

Required fields: `id`, `kind: input-table`, `source`, `inputMode`, `name`.

```json
{
  "id": "it-budget-plan",
  "kind": "input-table",
  "inputMode": "view",
  "name": "Budget Plan Input",
  "source": { "kind": "empty", "connectionId": "<conn-uuid>" },
  "style": { "backgroundColor": "#FFFFFF", "borderRadius": "round", "borderColor": "#DCE4EE", "borderWidth": 1 },
  "columns": [
    { "id": "bp-department", "type": "text",   "name": "Department" },
    { "id": "bp-proposed",   "type": "number", "name": "Proposed Amount" },
    { "id": "bp-status",     "type": "text",   "name": "Approval Status",
      "values": ["Draft", "Submitted", "Approved", "Rejected"],
      "pills": "color-by-option" }
  ]
}
```

- **`name` is required** — omitting it (along with getting the column
  shape wrong, below) produces a generic `Invalid kind: "input-table"`
  with no hint which field is missing.
- `inputMode`: `"edit"` (editable in draft only), `"explore"` (editable
  in published version, restricted access), `"view"` (editable in
  published version, all access levels). Real harvested workbooks use
  `"view"` universally — prefer that unless you specifically want
  draft-only editing.
- **`source.kind: "empty"` still requires `connectionId`** — even though
  there's no real data query, the empty input-table is provisioned
  against a connection. Omitting it silently fails validation (generic
  `Invalid kind: "input-table"`, no field-level error).
  `source.kind: "linked"` (backed by an existing warehouse table) also
  exists but isn't re-verified here.
- **Column shape is `{id, type, name}` — the field is `type`, NOT
  `columnType`.** `type` values observed: `"text"`, `"number"`. This
  differs from the regular `table` element's columns (`{id, name,
  formula}`) — input-table columns have no `formula`, since their
  values come from user input, not a query.
- **Optional column fields `values` + `pills`**: `values: [...]` gives a
  fixed picklist of options; `pills: "color-by-option"` renders the
  column as colored status pills (great for an Approval Status /
  Status column) instead of a plain text cell.
- Also supports `filters`, `conditionalFormats` (see above), `sort`,
  `summary`, and the styled title-section `name` / `noDataText`.
- **Input-tables start genuinely empty** — there is no way to pre-seed
  rows via the spec (they're populated by live user writes or an
  `insert-rows` button action, never by a query). Design around this:
  either accept the empty-start UX (a "start typing your plan" grid) or
  add an explicit seeding button.
- **Every input-table must be placed in the layout**, even if it's not
  meant to be a page's visual focus — park it on a page with
  `"visibility": "hidden"` if it exists purely as an action target.
  Omitting it from the layout entirely fails with `element '<id>' is
  not placed in layout`.

## Cross-references

- `reference/conventions.md` → "Passthrough mandate" — every table
  that's a source for downstream elements should declare full
  passthrough columns.
- `reference/conventions.md` → "Explicit-`name` rule" — every
  passthrough column needs an explicit `name`.
- `reference/conventions.md` → "Summary-bar pattern" — use
  `summary` for aggregate-then-categorize compositions.
- `formulas.md` — column reference rules + the #1 mistake.
