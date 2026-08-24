# Office of Finance — Notes

## Goal

Test bed for the `sigma-office-of-finance` skill (`.claude/skills/sigma-office-of-finance/`).
As of 2026-08-24 this is a 4-page workbook: Budget vs. Actual & Variance
(restyled), P&L Statement (new), General Ledger (new), and Rolling
Forecast (newly built — the skill's "forecasting module," previously
blocked on a missing `sigma-input-table-app` dependency, now ported).
Financial Close/Reconciliation is drafted in the skill's `structure.md`
but still has no build script — deprioritized this round, see "Open
decisions" below.

Aesthetic system: ported from `sigma-input-table-app`'s verified
"restrained light + comparison-delta KPI" look (navy/teal/coral accents,
pill-radius cards) rather than `sigma-company-dashboard-v2`'s
brand/logo/SVG-gradient system, which turned out to be mostly bank-
lending-specific and not reusable here. See
`.claude/skills/sigma-office-of-finance/scripts/style.py`.

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

| 2026-08-24 | `20260824-2105-workbook-full.json` | (this session, chat-only — no prompt file) | PUT succeeded on the combined 4-page, 48-element spec; `verify-workbook.sh` reports all 48 compiling clean. Ported `sigma-input-table-app` skill; added `scripts/style.py`; new `sql/pl_statement.sql` + `sql/general_ledger.sql`; fixed `sql/rolling_forecast.sql`'s unquoted (and therefore uppercase, non-passthrough-matching) column aliases. | (1) `comparison` on a `kpi-chart` with only a period/date column is rejected live ("requires a comparison column or period comparison") — contra `sigma-input-table-app`'s own SKILL.md text; fixed by always pairing `comparison` with an explicit `comparisonColumn` sibling, or omitting it when no natural baseline pair exists. (2) Sourcing KPIs/charts directly from an `input-table` element (per that skill's DEFAULT #3) triggered a masked `Invalid kind: "input-table"` on the input table itself; fixed by inserting a derived "Book" `table` between the input table and every downstream KPI/chart, matching the skill's own *verified* example script (`examples/build_demand_planning_lite.py`) rather than its prose. (3) The Rolling Forecast page's "verified foundation" (base → scenario-list → cross-join pivot → linked input table) is for the *multi-scenario* case; a single-implicit-scenario grid links straight from the base table with no pivot. (4) `pl_statement.sql`'s KPI formulas originally filtered on `[Line Item] = "Revenue"` etc. — switched to numeric `[Line Order] = 1` filters instead, more robust to a label rename. (5) One PUT attempt (workbook name `"Office of Finance"`, no suffix) got `cf-mitigated: challenge` (Cloudflare bot-management 403, never reached the Sigma API) on every retry; a fresh, never-before-submitted name string went through on the first try — looked like a per-value cooldown from this session's own repeated debugging traffic, not a real content problem. Renamed to `"Office of Finance Workbook"`. | Yes — see `reference/history.md` → "2026-08-24" entries. Documented the `comparisonColumn` requirement and the input-table/Book pattern in `history.md` (no dedicated spec-reference file changed this round — flagged as a follow-up: `sigma-input-table-app`'s own docs should probably note the Book-table indirection explicitly rather than leaving it implicit in one example script). |

## Open decisions carried over from the prompt

1. **Resolved 2026-08-21 (kiel): ship as-is.** `bar-variance-by-department`
   stays a plain bar chart substituting for the requested variance-bridge/
   waterfall look (unsupported by workbooks-as-code) — not holding for a
   real waterfall built in the UI.
2. **Resolved 2026-08-21 (kiel): leave the "FY26" placeholder.** Fiscal
   period label in the page title will be swapped later, before this goes
   in front of anyone.
3. Still open — visual verification (does it actually *look* right, does
   data actually render post-fix) hasn't happened yet for ANY of the 4
   pages — structural validation (`validate-spec.py`) and compile-check
   (`verify-workbook.sh`) have run for all of them, but nobody has opened
   the workbook and looked at it. Open the URL below and eyeball every
   page before promoting anything to `examples/`.
4. **New, not yet decided:** Financial Close/Reconciliation (the skill's
   drafted Page 2) was left out of this round — same incremental cost as
   the other pages now that the styling system exists, but wasn't asked
   for explicitly. Build it too, or leave the workbook at 4 pages?
5. **New, cosmetic:** the workbook's *display name* is still "Office of
   Finance — Budget vs. Actual & Variance (DRAFT)" — the very first name
   it was ever POSTed with. `PUT /v2/workbooks/{id}/spec` does not appear
   to update the top-level `name` field (only `document`), even though
   `name` is nominally part of the request body — the returned `get-meta`
   name never changed across any PUT in this session regardless of what
   `name` was sent. Renaming may need the UI, or a different endpoint —
   not investigated further this round.
6. **New:** the Rolling Forecast page builds the core linked-input-table
   loop only (seeded Base Case, editable Forecast Entry, Δ, comparative
   KPIs, baseline-vs-forecast chart) — not `sigma-input-table-app`'s full
   scenario create→submit→approve modal lifecycle. Layer that on later if
   the workbook needs multiple named scenarios rather than one editable
   grid.

## Promoted patterns

- `reference/schema-2026-08-breaking-changes.md` (in
  `sigma-workbook-conventions`) — see 2026-08-21 iteration log entries.
  This is the big one: it was entirely missing from the skill and would
  have broken every future build, not just this one.
- `scripts/validate-spec.py` — `document`-envelope normalization +
  `<Element>`/`<Container>` tag support (so the validator covers both
  schema generations) + `sql-source-trailing-semicolon` check
  (14 checks total).
- `reference/specification/sources.md` — "sql — custom SQL query"
  section documenting the trailing-semicolon gotcha (this source kind
  had no real documentation before).
- `.claude/skills/sigma-input-table-app/` — ported wholesale from the
  same source zip as `sigma-office-of-finance` and `sigma-company-
  dashboard-v2` two sessions ago; genuinely reusable, unlike the latter.
- `.claude/skills/sigma-office-of-finance/scripts/style.py` — the shared
  aesthetic system, usable by any future page this skill builds.
- `reference/history.md` (in `sigma-workbook-conventions`) — 2026-08-24
  entries on `comparisonColumn`, the input-table/Book pattern, and the
  Cloudflare per-value-cooldown observation.

## Live test workbook

- `workbookId`: `759ddb59-8b5c-4d80-a431-fe24773c483d`
- URL: https://staging.sigmacomputing.io/papercranestaging/workbook/3zWf4duUuzr3gFHmRt2xYh
- Folder: `Papercrane Staging/Solutions/claude-roundtrip-tests`
- 4 pages, 48 elements, all compiling clean per `verify-workbook.sh`.
  Display name still says "(DRAFT)" — see open decision #5 above.
