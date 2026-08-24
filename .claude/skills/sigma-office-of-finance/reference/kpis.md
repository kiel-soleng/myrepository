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

## P&L Statement

Filter by the numeric `Line Order` column (see `structure.md`), not a
quoted `Line Item = "..."` string match.

| KPI | Formula | Format | Depends on |
|---|---|---|---|
| Revenue | `SumIf([Amount], [Line Order] = 1)` | Currency, `$.3~s` | `Amount`, `Line Order` |
| Gross Margin % | `SumIf([Amount], [Line Order] = 3) / SumIf([Amount], [Line Order] = 1)` | Percent, 1 decimal | Gross Profit line, Revenue |
| Operating Margin % | `SumIf([Amount], [Line Order] = 8) / SumIf([Amount], [Line Order] = 1)` | Percent, 1 decimal | Operating Income line, Revenue |
| Net Income | `SumIf([Amount], [Line Order] = 10)` | Currency, `$.3~s` | `Amount`, `Line Order` |

`Line Order` values above (1=Revenue, 3=Gross Profit, 8=Operating Income,
10=Net Income) match `sql/pl_statement.sql`'s emitted rows exactly — if
that SQL's line set changes, update both places.

## General Ledger

| KPI | Formula | Format | Depends on |
|---|---|---|---|
| Total Debits | `Sum([Debit])` | Currency, `$,.0f` | `Debit` |
| Total Credits | `Sum([Credit])` | Currency, `$,.0f` | `Credit` |
| Net (Dr − Cr) | `Sum([Debit]) - Sum([Credit])` | Currency, signed — should read ~$0 on a balanced ledger | above two |
| Entry Lines | `Count([Entry ID])` | Integer | `Entry ID` |

Total Debits' comparison-delta baseline is Total Credits — the natural
trial-balance pairing, and directly shows whether the ledger is balanced.

## Page 2 — Financial Close / Reconciliation

| KPI | Formula | Format | Depends on |
|---|---|---|---|
| Open Exceptions | `CountIf([Status] <> "Resolved")` | Integer | `Status` |
| Aged Exceptions (count) | `CountIf([Status] <> "Resolved" AND [Days Open] > 5)` | Integer | `Days Open`, `Status` |
| Aged Exceptions (%) | `[Aged Exceptions] / [Open Exceptions]` | Percent, 0 decimals | above |
| Days Open (row-level) | `TODAY() - [Exception Opened Date]` | Integer (days) | `Exception Opened Date` |
| Days to Close | `[Actual Close Date] - [Period End Date]` (or `TODAY() - [Period End Date]` if still open) | Integer (days) | `Actual Close Date`, `Period End Date` |
| Accounts Reconciled (%) | `CountIf([Reconciliation Status] = "Reconciled") / Count([Account])` | Percent, 0 decimals | `Reconciliation Status` |

## Rolling Forecast

Built against `sigma-input-table-app`'s linked-input-table pattern (now
ported into this repo — no separate `scenario-modeler-pattern.md` file
exists even there; the skill's own `SKILL.md` + verified example script
are the source of truth). KPIs source from the derived "Book" table, not
the input table directly — see `structure.md`.

| KPI | Formula | Format | Depends on |
|---|---|---|---|
| Projected Forecast | `Sum([Effective Forecast])`, `comparisonColumn` → `Sum([Base Case])` | Currency, `$.3~s` | `Effective Forecast`, `Base Case` |
| Uplift % | `(Sum([Effective Forecast]) - Sum([Base Case])) / Sum([Base Case])` | Percent, 1 decimal | above |
| Baseline (Run-Rate) | `Sum([Base Case])` | Currency, `$.3~s` | `Base Case` |

`Effective Forecast = Coalesce([Forecast Entry], [Base Case])` and
`Δ vs. Base Case = [Effective Forecast] - [Base Case]` are declared as
row-level formula columns directly on the linked input table (bare
sibling references are correct there — see `structure.md`).

## Cross-page reconciliation note

Budget vs. Actual's department/category dimension, P&L Statement's line
items, and Rolling Forecast's forecast dimension all use the same
department/category labels and the same seed constants (see
`sql/budget_actuals.sql` and `sql/pl_statement.sql`) — if a prospect's
chart of accounts differs from the demo default, remap once at the top
of the data-prep SQL, not per-page, so the pages stay comparable.
