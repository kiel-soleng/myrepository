# Sources (non-warehouse)

Source kinds other than `warehouse-table` — for warehouse-table see
`sources-warehouse.md`.

```bash
jq -r '.components.schemas | keys[] | select(test("Source"))' /tmp/sigma-api.json
jq '.components.schemas.JoinSource, .components.schemas.SqlSource, .components.schemas.DataModelSource' /tmp/sigma-api.json
```

Every element with columns has a `source` that defines where its data
comes from. This file focuses on the **patterns** and **formula-prefix
conventions** for each non-warehouse source kind.

For discovery (finding connection IDs, paths, data model IDs, element
IDs), see `reference/workflows/discover.md`.

---

## table — cross-element reference

Sources another element in the same workbook. This is the most common
source kind for charts, KPIs, and derived tables.

```json
{
  "kind": "table",
  "elementId": "<id of another element on some page>"
}
```

Column formulas reference that element's columns using its `name`:

- Element named "Sales Table" → `[Sales Table/Revenue]`

The cross-element resolver looks up by display name; if the source
element's `name` changes, every dependent formula breaks. See
`reference/conventions.md` → "Rename-cascade corollary."

### Optional `groupingId`

For a chart sourcing a table with `groupings`, pin the chart to a
specific grouping level via:

```json
{
  "kind": "table",
  "elementId": "<table-id>",
  "groupingId": "<grouping-id>"
}
```

This makes the grouping's columns directly accessible as local
references (`[Total Profit Margin]` without the sibling prefix).
Sigma's GET round-trip sometimes strips `groupingId`; charts still
render at the grouping's grain when every referenced column is
itself grain-anchored (`groupBy` or grouping calc), so omitting the
explicit `groupingId` is not fatal — but include it when the chart
needs local-name access.

---

## data-model

References an element from an existing data model. **Prefer this
source kind when the user's org has relevant data models** — it
inherits the data model's joins, filters, and column-level security.

```json
{
  "kind": "data-model",
  "dataModelId": "<data-model-uuid>",
  "elementId": "<element-uuid within that model>"
}
```

Column formulas can reference:

- Data-model element columns: `[<DataModelElementName>/<column>]`
- Data-model metrics: `[Metrics/<metric-name>]` — see
  `reference/conventions.md` → "`[Metrics/<Name>]` resolution"

Discover available data models with
`scripts/api/mcp-search.sh "<topic>" --types dataModel`. Inspect a
specific model's elements + metrics with
`scripts/api/mcp-describe.sh datamodel-element <dm-id> <el-id>`.

If no data model fits, fall back to `warehouse-table` — don't
manufacture a model.

---

## join

Joins multiple warehouse tables into one logical source. Specify a
`primarySource` and an array of `joins`. Each join has `left`,
`right`, `columns` (the join keys), `name` (used as the prefix in
column formulas), and `joinType`.

```json
{
  "kind": "join",
  "name": "Sales Star",
  "primarySource": {
    "kind": "warehouse-table",
    "connectionId": "<conn-uuid>",
    "path": ["DB", "SCHEMA", "F_POS"]
  },
  "joins": [
    {
      "name": "Sales",
      "joinType": "left-outer",
      "left": {
        "kind": "warehouse-table",
        "connectionId": "<conn-uuid>",
        "path": ["DB", "SCHEMA", "F_POS"]
      },
      "right": {
        "kind": "warehouse-table",
        "connectionId": "<conn-uuid>",
        "path": ["DB", "SCHEMA", "F_SALES"]
      },
      "columns": [
        { "left": "[Order Number]", "right": "[Order Number]" }
      ]
    }
  ]
}
```

`joinType` values: `inner`, `left-outer`, `right-outer`, `full-outer`,
`cross`.

### Column formula prefixes with joins

- **Primary-source columns** use the **join's top-level `name`**:
  `[Sales Star/Order Number]`
- **Joined-table columns** use the **join leg's `name`**:
  `[Sales/Cust Key]`
- **Warehouse path segments are NOT used** as prefixes inside a join
  — use the join leg's `name` instead.

See `formulas.md` → "Column reference rules" → "Join source" for the
full prefix rules.

---

## union

Combines two or more warehouse-table or element sources into a single
source whose columns are explicitly mapped via `matches[]`.

```json
{
  "kind": "union",
  "name": "All Sales",
  "sources": [
    {
      "kind": "warehouse-table",
      "connectionId": "<conn-uuid>",
      "path": ["DB", "SCHEMA", "JULY_SALES"]
    },
    {
      "kind": "warehouse-table",
      "connectionId": "<conn-uuid>",
      "path": ["DB", "SCHEMA", "AUGUST_SALES"]
    }
  ],
  "matches": [
    {
      "outputColumnName": "Order ID",
      "sourceColumns": ["[Order ID]", "[Order ID]"]
    },
    {
      "outputColumnName": "Sales",
      "sourceColumns": ["[Sales]", "[Sales]"]
    }
  ]
}
```

`sourceColumns` is an array aligned to `sources` — one entry per
source, in order. `outputColumnName` becomes the column users see
and the name your element formulas reference.

**Set `name` explicitly.** Formula prefixes for the consuming
element use the union's `name`, e.g. `[All Sales/Order ID]`. If you
omit `name`, Sigma assigns `"Union of N Sources"`; if your element
also defines a column whose `name` matches an `outputColumnName`, a
bare `[Order ID]` formula becomes a circular self-reference and the
SQL fails to compile.

---

## Other source kinds

These exist but are less common; model the shape off an existing
workbook's spec via
`scripts/api/publish-workbook.sh get-spec <wb-id>`:

- `sql` — custom SQL query. See below — verified 2026-09-09,
  round-trips cleanly.
- `transpose` — transposes rows/columns.

### `sql` — custom SQL query (verified 2026-09-09)

```json
{
  "kind": "sql",
  "connectionId": "<conn-uuid>",
  "statement": "SELECT ... AS \"Student Id\", ... FROM ..."
}
```

Confirmed against Sigma's published data-model OpenAPI
(`CreateDataModelSpecPagesItemsElementsItemsOneOf0Source2` in
`https://help.sigmacomputing.com/openapi/code-representation.json`)
and against a live workbook POST — same 3-field shape on both the
workbook and data-model endpoints.

**⚠️ Column-reference prefix is the literal string `Custom SQL` — NOT
the element's own `name`.** This is the one source kind that breaks
the "prefix = element's `name`" pattern every other kind follows.
Verified by bisecting a real POST failure (`Dependency not found:
'students/student id'` when using the element's own name as prefix)
against a harvested real workbook, whose `sql`-sourced table's own
columns all reference `[Custom SQL/<Column>]` regardless of what the
table element itself is named:

```json
{
  "id": "tbl-students",
  "kind": "table",
  "name": "Students",
  "source": { "kind": "sql", "connectionId": "<conn-uuid>", "statement": "SELECT 'S00001' AS \"Student Id\"" },
  "columns": [
    { "id": "st-student-id", "name": "Student Id", "formula": "[Custom SQL/Student Id]" }
  ]
}
```

Downstream elements that source **from this table** (via
`{kind: "table", elementId: "tbl-students"}`) still use the table's own
`name` as normal — `[Students/Student Id]` — only the base table's
*own* passthrough columns need the `Custom SQL` prefix.

**Column-name resolution is exact-match, not friendly-cased.** Unlike
`warehouse-table` (which friendly-cases `student_id` → `Student Id`
for you), a `sql` source's columns resolve by **exact string match**
against the SQL's own output alias:

- Quote the SQL alias exactly as the desired display name —
  `AS "Student Id"` — and reference it verbatim: `[Custom SQL/Student Id]`.
  This is the recommended pattern; no normalization to reason about.
- An unquoted snake_case alias (`AS student_id`) must be referenced in
  its **raw, exact form**: `[Custom SQL/student_id]`. Referencing it as
  a friendly-cased `[Custom SQL/Student Id]` **fails** even though the
  same friendly-casing works fine for `warehouse-table`/`data-model`/
  `table` sources. Single-word aliases (`college`) seem to resolve
  case-insensitively either way (`College` or `college` both worked in
  testing) — but don't rely on that for multi-word names; the space in
  a friendly-cased multi-word reference doesn't exist in a snake_case
  raw name, so the two never actually match once there's an underscore
  involved.

See `reference/history.md` → "2026-09-09" for the full diagnostic
trail (the failure surfaces as a generic `Dependency not found` error
with no hint that it's a prefix or casing problem).

---

## Two-tier sourcing pattern

For workbooks where data needs derivation (cohort buckets, weeks-
since-first-action, comparative anchors) before visualization, build
TWO table elements on the same page:

1. **Raw table** sourced from the warehouse/data-model element.
   Carries the base columns + any first-order calculated columns.
2. **Derived table** sourced from the raw table via
   `kind: table, elementId: <raw-id>`. Carries the cohort dimensions
   and the final-grain columns.

KPIs, charts, and pivots source from the derived table. This keeps
the first-order math out of the viz elements (avoiding recursive
aggregation) and makes the derivation chain inspectable.

Canonical example: `examples/data-model-sourced-cohort-pivot.json`.

See `reference/conventions.md` → "Two-tier sourcing" for the rule
detail.

---

## Basket / co-occurrence / self-join patterns

"Which products are frequently purchased together?" — the classic
market-basket ask — needs a self-join of the transaction table on
`Order Number` to produce (Product A, Product B) pairs.

**Sigma's `join` source is warehouse-only** — it operates on warehouse
tables, not workbook elements. Workbook-element self-joins on the fact
table are not directly supported at the spec layer today.

### Three practical approaches

**1. Warehouse-side prep (recommended for true basket analysis).**
Build a materialized view or dbt model that emits `(Order Number,
Product A, Product B, Attach Count)` tuples with `Product A != Product
B`. Source a workbook table from that view. Pivot Product A × Product
B with `Sum([Attach Count])` in `values`.

**2. Lookup-based attach rate (workbook-only, single-anchor).**
Pick one anchor category. Add a `Contains-Anchor?` boolean to a raw
transaction table via `Lookup()` on Order Number. Aggregate other
product types conditional on the anchor being in the order:

```
Attach Count for Peer =
  CountDistinct(If([Order Has Anchor] And [Product Type] = "<peer>",
                    [Order Number], Null))
```

This gives attach rates for one fixed anchor at a time. Multiple
anchors = multiple derived tables. Doesn't scale beyond a few anchors
but works purely at the workbook layer.

**3. Order-cardinality diagonal (fastest to build, weakest signal).**
Aggregate orders by (Product Type, other-dimension) with
`CountDistinct(Order Number)`. Pivot Product Type × Product Type
(same column aliased in two `columns[]` entries with different names)
shows only the DIAGONAL — how many orders per single category — not
true cross-sell. Ship this as a placeholder if the warehouse work
isn't scoped yet, but be explicit in the workbook description that
it's not a true co-occurrence view.

Verified 2026-07-02 against `Product-and-Basket-Performance` build,
which shipped approach (3) as an honest simplification. True
basket analysis in that data model requires approach (1).

### When to ship a workaround vs push back

If the user asks for basket analysis and:
- The warehouse already has an orders-x-orders view → source from it
  (approach 1).
- The warehouse doesn't → surface the constraint in the plan's Open
  Decisions and propose either warehouse prep OR the single-anchor
  attach-rate pattern (approach 2). Approach 3 is only appropriate
  as an interim visualization with explicit caveating.

---

## Choosing the right source kind

| Need | Source kind | Notes |
|---|---|---|
| Raw warehouse access | `warehouse-table` | See `sources-warehouse.md` |
| Inherit data-model joins, filters, metrics | `data-model` | Use `[Metrics/<X>]` for metric refs |
| Source from another workbook element | `table` | Most common for derived tables, charts, KPIs |
| Combine multiple warehouse tables via join keys | `join` | When the warehouse has no joined view |
| Stack same-schema data row-wise | `union` | When tables share columns across time/region |
| Custom SQL query | `sql` | Last resort — harder to maintain |
| Pivot/unpivot warehouse data | `transpose` | Rare — usually do in warehouse layer |

Default: `data-model` if available; `warehouse-table` otherwise; `table`
for any downstream element sourcing another element on the same page.
