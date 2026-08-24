# Canonical page structure — Office of Finance

Five pages. Each is independently useful, so partial builds are valid —
e.g. a close-only demo for a controller persona, or skip Financial Close
entirely (it's the lowest-priority page here; see its section below).
All built pages so far live in one workbook, assembled by
`workbooks/office-of-finance/build_workbook.py`.

Aesthetic system for every page: `.claude/skills/sigma-office-of-finance/
scripts/style.py` (ported from `sigma-input-table-app`'s verified
restrained-light + comparison-delta look — navy/teal/coral accents,
pill-radius cards). Do NOT reach for `sigma-company-dashboard-v2`'s brand/
logo/gradient system — it's bank/lending-branding-specific and doesn't fit
this domain.

## Page 1 — FP&A Budget vs. Actual & Variance

**Required elements:**
- Header with fiscal-period control (e.g. month/quarter picker) driving every
  element below.
- KPI row (4): Total Budget, Total Actual, Variance $ (signed), Variance %
  (signed) — each a comparative gradient KPI vs. prior period.
- Variance bridge / waterfall chart by department or GL category (mirrors
  the shape of `sigma-company-dashboard-v2/sql/nim_bridge.sql`'s bridge
  pattern, adapted to budget→actual steps instead of revenue→profit steps).
- Department/cost-center table: Budget, Actual, Variance $, Variance %, one
  row per department, sorted by |Variance $| descending so the biggest
  misses surface first.
- Trend chart: Budget vs. Actual by month, trailing 12 months.

**Optional:**
- Drill-through control from the department table to a GL-line-item detail
  table.

## Page — P&L Statement

Built 2026-08-24 (`workbooks/office-of-finance/build_pl.py`,
`sql/pl_statement.sql`). Extends `budget_actuals.sql`'s department/
account-type seed constants (rather than inventing disconnected numbers)
so this page's Revenue/Opex figures reconcile with Page 1's by
construction.

- **Data shape:** long-format rows (`Period Month, Line Order, Section,
  Line Item, Amount`) — Sigma tables have no native mid-table subtotal-row
  support, so subtotal rows (Gross Profit, Operating Income, Net Income)
  are precomputed in SQL and emitted as ordinary rows. `Line Order` is
  required so the statement can be sorted into correct accounting order.
- **Statement table:** use a `pivot-table` with `rowsBy: [{id: <line-item
  col>, sort: {by: <line-order col>, direction: "ascending"}}]`, NOT a
  plain `table` — plain tables have no row-sort field (`order` on a table
  only controls left-to-right *column* order), so row order would be
  whatever Sigma's own aggregation happens to produce.
- **KPI row (4):** Revenue, Gross Margin %, Operating Margin %, Net
  Income. Filter each line item by the numeric `Line Order` value, not a
  quoted `Line Item = "..."` string match — more robust to a label
  rename, and avoids stacking multiple quoted-string comparisons next to
  an embedded multi-`UNION ALL SELECT` custom-SQL statement in one
  request body (see `reference/history.md` → 2026-08-24 for why that
  combination is worth avoiding).
- **Trend chart:** Revenue and Net Income by month, off a second
  unfiltered copy of the source table (same double-table pattern as
  Page 1).

## Page — General Ledger

Built 2026-08-24 (`workbooks/office-of-finance/build_gl.py`,
`sql/general_ledger.sql`). Genuinely distinct from Financial Close's
exceptions table below — this is transaction-level journal-entry detail
(one row per debit/credit line), not a reconciliation punch-list.

- **Data shape:** journal-entry-line grain (`Entry ID, Entry Date,
  Category, Account, Description, Debit, Credit`) — balanced by
  construction (every `Entry ID` contributes exactly one debit row and
  one credit row of equal amount), so `Sum(Debit) = Sum(Credit)` across
  the whole table is a real correctness signal, not just decoration.
- **KPI row (4):** Total Debits (comparison-delta vs. Total Credits —
  the natural trial-balance pairing), Total Credits, Net (Dr − Cr, should
  read ~$0), Entry Lines (count).
- **Trial balance:** a `pivot-table` (`rowsBy: [{id: <account col>, sort:
  ...}]`, `values: [debit, credit, net]`) rolling up by account.
- **Detail table:** filterable by category/account controls, one row per
  journal-entry line.

## Page — Rolling Forecast ("the forecasting module")

Built 2026-08-24 (`workbooks/office-of-finance/build_forecast.py`,
`sql/rolling_forecast.sql`) using `sigma-input-table-app`'s verified
linked-input-table pattern (that skill is now ported into this repo).
Builds the core seeded-Base-Case + editable-grid + comparative-KPI loop —
**not** the full scenario create/submit/approve modal lifecycle that
skill's SKILL.md also documents; that's a real scope increase, a stated
follow-up, not built here.

Two corrections against `sigma-input-table-app`'s own SKILL.md *prose*,
found by following its *verified example* instead
(`examples/build_demand_planning_lite.py`) — see `reference/history.md`
→ 2026-08-24 for the full incident:

- **No pivot/cross-join needed for a single implicit scenario.** The
  "base → scenario-list → cross-join pivot → linked input table" chain in
  that skill's "verified foundation" is for the *multi-scenario* case.
  When there's exactly one editable grid (this page), the linked input
  table sources directly from the base table (`source: {"kind":
  "linked", "from": <base-table-id>}`) — the base table is already at the
  right grain (one row per month × department).
- **Every downstream KPI/chart sources from a derived "Book" table, not
  the input table directly.** Parenting KPIs/charts straight to the
  `input-table` element (as that skill's DEFAULT #3 literally instructs)
  produced a masked `Invalid kind: "input-table"` on the input table
  itself at PUT time. Insert one plain `table` sourced from the input
  table (`source: {"elementId": <input-table-id>, "kind": "table"}`,
  redeclaring every needed column), and point every KPI/chart at that
  instead — exactly what the verified example script does, despite its
  own skill's prose claiming otherwise.
- **`inputMode: "view"`, not `"edit"`.** Per `schema-2026-08-breaking-
  changes.md`'s permission table, `"edit"` is editable in **draft only**;
  `"view"` is editable in the **published** workbook at all access
  levels — since this workbook is PUT straight to its published/live
  state, `"view"` is correct here.
- **Required:** hidden `Base Case` seed column, editable `Forecast Entry`
  column, `Effective Forecast = Coalesce([Forecast Entry], [Base Case])`,
  a Δ formula column, and `stacking: "none"` on the baseline-vs-forecast
  chart (two y-series stack by default and silently render their SUM).

## Page — Financial Close / Reconciliation (lowest priority — not yet built)

**Required elements:**
- KPI row (4): Open Exceptions (count), Aged Exceptions (`> 5 business days
  open`, count + %), Days to Close (current period, vs. target), Accounts
  Reconciled (%).
- Close calendar / checklist table: task, owner, due date, status
  (Not Started / In Progress / Done / Blocked), days until due (or overdue).
- Exceptions table: account, exception type, amount, age (days open),
  owner, status — sortable/filterable by age and status.
- Reconciliation status by account-category chart (e.g. stacked bar:
  reconciled vs. open, by category).

`sql/close_exceptions.sql` already exists for this page (trailing-
semicolon bug already fixed) — only the build script is missing.

**Optional:**
- Notification/alert element for exceptions aged past a threshold (see
  `sigma-company-dashboard-v2/scripts/add_notifications.py` for the
  notification-element shape — but note `sigma-company-dashboard-v2`
  itself is not used elsewhere in this skill; only borrow this one
  reference if genuinely needed).
