# Worked examples

These show the gap between a vague prompt and a plan Builder can actually execute
well. In each case, assume `search`/`describe` were already called and returned the
identifiers shown — in a real conversation you'd get these from the tools, not
from memory.

---

## Example 1 — Single-page KPI dashboard

**User prompt:** "Build a quick sales overview off the Sales Ops data model. Top-line
numbers and a trend, nothing fancy."

**What NOT to do:** write a plan that just says "Build Outline: KPIs for sales,
a chart of sales over time." Builder needs real column/metric names and a
real layout, not restated vagueness.

**Good plan body:**

```markdown
# Goal

Give the sales team a fast read on overall performance — current totals and
whether the trend is up or down — without digging into a full data model.

# Decisions

- Source: `Sales Ops` data model, `Orders` element (data-model-element,
  described this conversation).
- Metrics: `Revenue` (sum) and `Order Count` (count), both available as
  pre-defined metrics on the `Orders` element.
- Time grain: monthly, using the `Order Date` column.
- No filters requested — show all-time data with a date-range control so the
  user can narrow it themselves.

# Existing State

Empty workbook.

# Build Outline

1. Date range control bound to `Order Date` on the `Orders` element.
2. KPI: `Revenue` (metric `revenue`), formatted as currency, reflecting the
   control's date range.
3. KPI: `Order Count` (metric `order_count`), reflecting the same range.
4. Line chart: `Revenue` by month (`Order Date` truncated to month on the
   x-axis), reflecting the same range.

# Layout

Date range control across the top, full width. Below it, the two KPIs
side by side. Below the KPIs, the line chart spanning the full width.
```

**sources:** `[{ kind: "datamodel-element", inodeId: "<Sales Ops inodeId>", nodeId: "<Orders elementId>" }]`

---

## Example 2 — Multi-page dashboard

**User prompt:** "I want a workbook that looks at profitability by product line
on one page, and customer attrition on another."

**What makes this a two-page plan, not two separate workbooks:** the user asked
for one workbook with two views — say so explicitly in Goal so Builder doesn't
split it into two files.

**Good plan body (abridged):**

```markdown
# Goal

One workbook covering two related but distinct questions: which product
lines are profitable, and which customers are at risk of churning.

# Decisions

- Page 1 source: `Profitability` data-model element — `Gross Margin` and
  `Revenue` metrics, broken down by `Product Line`.
- Page 2 source: `Customer Health` data-model element — `Last Order Date`
  and `Churn Risk Score` columns.
- Two pages in one workbook, not two workbooks.

# Existing State

Empty workbook.

# Build Outline

Page 1 — Profitability:
1. Bar chart: `Gross Margin` by `Product Line`, sorted descending.
2. Table: `Product Line`, `Revenue`, `Gross Margin`, `Gross Margin %`.

Page 2 — Customer Attrition:
1. KPI: count of customers where `Churn Risk Score` > 70.
2. Table: `Customer Name`, `Last Order Date`, `Churn Risk Score`, sorted by
   risk descending.

# Layout

Page 1 ("Profitability"): bar chart on the left half, table on the right
half. Page 2 ("Customer Attrition"): KPI band across the top, table below
spanning full width.
```

---

## Example 3 — Ad-hoc single chart, no data model

**User prompt:** "Chart monthly signups from the `app_db.public.users` table."

This is a warehouse table, not a data model — so `sources` uses `kind: "table"`,
and there's no `describe(type: "datamodel-element", ...)` step, just
`describe(type: "table", inodeId)` to confirm the column name and type for the
signup timestamp.

**Good plan body:**

```markdown
# Goal

Show signup volume over time from the raw users table.

# Decisions

- Source: `app_db.public.users` table (warehouse table, described this
  conversation — confirmed `created_at` is a timestamp column).
- Grain: monthly.

# Existing State

Empty workbook.

# Build Outline

1. Bar chart: count of rows by `created_at` truncated to month.

# Layout

Single chart, centered, full width of the page.
```

**sources:** `[{ kind: "table", inodeId: "<users table inodeId>" }]`

---

## Pattern to take away

Every good plan:
- Names real columns/metrics from `describe` output, never invented ones.
- States the source's *kind* (table vs. datamodel-element) explicitly, since
  that determines the `sources` entry shape.
- Keeps Goal business-oriented and Build Outline implementation-oriented — don't
  blur the two.
- Says "Empty workbook" in Existing State every time — `build_workbook` always
  starts fresh.
- Describes Layout in spatial prose (top/bottom, left/right, full-width vs.
  side-by-side) rather than pixel coordinates — Builder translates this into a
  real grid.
