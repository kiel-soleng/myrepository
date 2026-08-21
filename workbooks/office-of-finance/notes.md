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

## Open decisions carried over from the prompt

1. **Resolved 2026-08-21 (kiel): ship as-is.** `bar-variance-by-department`
   stays a plain bar chart substituting for the requested variance-bridge/
   waterfall look (unsupported by workbooks-as-code) — not holding for a
   real waterfall built in the UI.
2. **Resolved 2026-08-21 (kiel): leave the "FY26" placeholder.** Fiscal
   period label in the page title will be swapped later, before this goes
   in front of anyone.
3. Still open — visual verification (does it actually *look* right) hasn't happened —
   only structural validation (`validate-spec.py`) and compile-check
   (`verify-workbook.sh`) have run. Open the workbook URL below and
   eyeball it before promoting to `examples/`.

## Promoted patterns

- `reference/schema-2026-08-breaking-changes.md` (in
  `sigma-workbook-conventions`) — see iteration log above. This is the
  big one: it was entirely missing from the skill and would have broken
  every future build, not just this one.
- `scripts/validate-spec.py` — `document`-envelope normalization +
  `<Element>`/`<Container>` tag support, so the validator covers both
  schema generations.

## Live test workbook

- `workbookId`: `759ddb59-8b5c-4d80-a431-fe24773c483d`
- URL: https://staging.sigmacomputing.io/papercranestaging/workbook/3zWf4duUuzr3gFHmRt2xYh
- Folder: `Papercrane Staging/Solutions/claude-roundtrip-tests`
- Still named "(DRAFT)" — rename once visually verified and open
  decisions above are resolved.
