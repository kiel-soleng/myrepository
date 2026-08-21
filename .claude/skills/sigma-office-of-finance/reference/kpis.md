# Canonical KPIs — Office of Finance

Formulas use Sigma function syntax. Prefer `[Metrics/<Name>]` when the data
model already defines the metric; these are the fallback hand-derivations.

## Page 1 — Budget vs. Actual & Variance

| KPI | Formula | Format | Depends on |
|---|---|---|---|
| Total Budget | `Sum([Budget Amount])` | Currency, 0 decimals | `Budget Amount` |
| Total Actual | `Sum([Actual Amount])` | Currency, 0 decimals | `Actual Amount` |
| Variance $ | `Sum([Actual Amount]) - Sum([Budget Amount])` | Currency, signed, 0 decimals | above two |
| Variance % | `([Variance $]) / Sum([Budget Amount])` | Percent, signed, 1 decimal | `Variance $`, `Total Budget` |
| Variance $ (row-level, for department table) | `[Actual Amount] - [Budget Amount]` | Currency, signed | row-level |
| Variance % (row-level) | `[Variance $] / [Budget Amount]` | Percent, signed | row-level |

Color rule: for expense/cost-center rows, positive variance (over budget) is
"bad" (red); for revenue rows, positive variance (over budget) is "good"
(green). Don't apply one color rule workbook-wide — branch on account type.

## Page 2 — Financial Close / Reconciliation

| KPI | Formula | Format | Depends on |
|---|---|---|---|
| Open Exceptions | `CountIf([Status] <> "Resolved")` | Integer | `Status` |
| Aged Exceptions (count) | `CountIf([Status] <> "Resolved" AND [Days Open] > 5)` | Integer | `Days Open`, `Status` |
| Aged Exceptions (%) | `[Aged Exceptions] / [Open Exceptions]` | Percent, 0 decimals | above |
| Days Open (row-level) | `TODAY() - [Exception Opened Date]` | Integer (days) | `Exception Opened Date` |
| Days to Close | `[Actual Close Date] - [Period End Date]` (or `TODAY() - [Period End Date]` if still open) | Integer (days) | `Actual Close Date`, `Period End Date` |
| Accounts Reconciled (%) | `CountIf([Reconciliation Status] = "Reconciled") / Count([Account])` | Percent, 0 decimals | `Reconciliation Status` |

## Page 3 — Rolling Forecast

Reuses `sigma-input-table-app`'s scenario-modeler KPI set with finance
naming. See that skill's `reference/scenario-modeler-pattern.md` for the
verified formula shapes (Coalesce/baseline seeding, Δ column, bulk-edit
button wiring) — not re-derived here.

| KPI | Formula | Format | Depends on |
|---|---|---|---|
| Total Forecast | `Sum(Coalesce([Forecast Entry], [Base Case]))` | Currency, 0 decimals | `Forecast Entry`, `Base Case` |
| Forecast Δ vs. Baseline | `[Total Forecast] - Sum([Base Case])` | Currency, signed | above |
| Forecast Accuracy (prior period) | `1 - Abs(Sum([Prior Forecast]) - Sum([Actual Amount])) / Sum([Actual Amount])` | Percent, 1 decimal | `Prior Forecast`, `Actual Amount` |

## Cross-page reconciliation note

Page 1's department/category dimension and Page 3's forecast dimension
should use identical category labels — if a prospect's chart of accounts
differs from the demo default, remap once at the top of the data-prep SQL,
not per-page, so the two pages stay comparable.
