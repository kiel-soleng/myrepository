# Canonical page structure — Office of Finance

Three pages. Build in this order; each is independently useful, so
`SURFACES`-style partial builds (see `sigma-company-dashboard-v2` HANDOFF §5b)
are valid here too — e.g. a close-only demo for a controller persona.

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

## Page 2 — Financial Close / Reconciliation

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

**Optional:**
- Notification/alert element for exceptions aged past a threshold (see
  `sigma-company-dashboard-v2/scripts/add_notifications.py` for the
  notification-element shape already verified in this repo).

## Page 3 — Rolling Forecast

Composes `sigma-input-table-app`'s verified scenario-modeler pattern
(baseline pivot → linked input table → projection formulas → comparison
KPIs → bulk-edit buttons). Do not re-derive that shape here; this page is
that pattern with finance-specific baseline and dimensions:

- **Baseline:** trailing-actuals run rate by GL category or department
  (not a generic "Revenue" column — use the same categories as Page 1's
  department table so the two pages reconcile).
- **Editable forecast grid:** analyst-entered forecast by category by
  future month, seeded with a hidden `Base Case` formula column per
  `sigma-input-table-app`'s "seed a LIVE Base Case" default so it isn't
  dead-empty on load.
- **Required:** Δ column (Forecast − Base Case), variance chart, forecast
  vs. prior-forecast comparison KPI (forecast accuracy signal).
- **Required:** `inputMode: "edit"` and `stacking: "none"` on the
  projected-vs-baseline chart — both are known input-table-app gotchas
  that silently break this exact shape.
