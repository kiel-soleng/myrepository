# Office of Finance — Notes

## Goal

Test bed for the `sigma-office-of-finance` skill (`.claude/skills/sigma-office-of-finance/`).
Page 1 (FP&A Budget vs. Actual & Variance) is the first pattern being
round-tripped and promoted toward a real exemplar; Pages 2–3 (Close/
Reconciliation, Rolling Forecast) are drafted in the skill but have no
build script or iteration yet.

## Data sources

- Book / primary source: synthetic — inline Custom SQL
  (`.claude/skills/sigma-office-of-finance/sql/budget_actuals.sql`), 5
  departments x 12 trailing months, no real warehouse table yet.
- Connection: `Snowflake` (`a9d45cfe-ff65-4515-8193-a7072602a1ee`),
  account `cxa94702` — the SQL is self-contained (CTEs only), so the
  connection just needs to be a live, reachable Snowflake account; it
  happens to resolve `SE_INTERNAL_DB.SCHEMA_KIEL` if a real-table swap
  is wanted later.
- Join key(s): n/a (single synthetic table, two copies — one filtered
  by the page's period control, one unfiltered for the trailing-12mo
  trend chart).

## Iteration log

| Date | Iteration file | Prompt file | What worked | What broke | Promoted to skill? |
|------|----------------|-------------|-------------|------------|--------------------|
| 2026-08-21 | `20260821-2017-page1-budget-variance.json` | `prompts/20260821-1246.md` | POST succeeded (`workbookId: 759ddb59-8b5c-4d80-a431-fe24773c483d`), all 13 elements compile clean per `verify-workbook.sh`. | (1) Draft was ported in from a checkout still on the pre-2026-08 flat top-level shape — this repo's live API now requires the `document{}` envelope, flat `document.elements`, and `<Element>`/`<Container>` layout tags. (2) `bar-variance-by-department` only carried 2 of 5 source columns — passthrough-coverage fail. (3) `ctrl-period` control was missing the required `name` field. (4) `kpi-chart.value` used `{id}` instead of `{columnId}` — rejected with `Invalid kind: "kpi-chart"`. (5) Chart axis used legacy `xAxis: {id}` / `yAxis: [{id}]` — rejected with `Invalid kind: "bar-chart"`; switched to modern `xAxis: {columnId}` / `yAxis: {columnIds}`. | Yes — see `reference/history.md` → "2026-08-21 — `document{}` envelope missing from this skill entirely". Ported `reference/schema-2026-08-breaking-changes.md` into the skill and added it to the "every build" required-reading row; patched `scripts/validate-spec.py` to normalize the `document` envelope and accept both old/new layout tag names. |
| 2026-08-21 | `20260821-2049-page1-budget-variance.json` | `prompts/20260821-1246.md` | PUT to the same workbook succeeded; all three `.sql` files' wrapping subquery now closes cleanly. | Opening the workbook in the UI surfaced a "warehouse error: query failed" on **every** element — `verify-workbook.sh` had reported all 13 as compiling clean, because it only checks the compiled SQL for unresolved-formula markers, not warehouse execution. Root cause: all three `sql/*.sql` files in the skill (`budget_actuals.sql`, `close_exceptions.sql`, `rolling_forecast.sql`) ended their final `SELECT` with a trailing `;`. Sigma wraps a custom-SQL `statement` as `select <cols> from (\n<statement>\n) Q1 limit 1000` — the semicolon lands right before the closing `)`, which is invalid on every warehouse, and since every element on the page sources from one of those two statements, all of them failed identically. | Yes — stripped the trailing `;` from all three `.sql` files; documented the gotcha in `reference/specification/sources.md` → "sql — custom SQL query"; added a 14th `validate-spec.py` check (`sql-source-trailing-semicolon`) so this is now caught pre-POST instead of only live in the UI. See `reference/history.md` for the full incident writeup. |

## Open decisions carried over from the prompt

1. **Resolved 2026-08-21 (kiel): ship as-is.** `bar-variance-by-department`
   stays a plain bar chart substituting for the requested variance-bridge/
   waterfall look (unsupported by workbooks-as-code) — not holding for a
   real waterfall built in the UI.
2. **Resolved 2026-08-21 (kiel): leave the "FY26" placeholder.** Fiscal
   period label in the page title will be swapped later, before this goes
   in front of anyone.
3. Still open — visual verification (does it actually *look* right, does
   data actually render post-fix) hasn't happened yet — structural
   validation (`validate-spec.py`), compile-check (`verify-workbook.sh`),
   and now the warehouse-execution fix have all run, but nobody has
   opened the workbook and looked at it. Open the URL below and eyeball
   it before promoting to `examples/`.

## Promoted patterns

- `reference/schema-2026-08-breaking-changes.md` (in
  `sigma-workbook-conventions`) — see iteration log above. This is the
  big one: it was entirely missing from the skill and would have broken
  every future build, not just this one.
- `scripts/validate-spec.py` — `document`-envelope normalization +
  `<Element>`/`<Container>` tag support (so the validator covers both
  schema generations) + new `sql-source-trailing-semicolon` check
  (14 checks total now).
- `reference/specification/sources.md` — new "sql — custom SQL query"
  section documenting the trailing-semicolon gotcha (this source kind
  had no real documentation before).

## Live test workbook

- `workbookId`: `759ddb59-8b5c-4d80-a431-fe24773c483d`
- URL: https://staging.sigmacomputing.io/papercranestaging/workbook/3zWf4duUuzr3gFHmRt2xYh
- Folder: `Papercrane Staging/Solutions/claude-roundtrip-tests`
- Still named "(DRAFT)" — rename once visually verified and open
  decisions above are resolved.
