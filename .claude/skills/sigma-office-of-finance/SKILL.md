---
name: sigma-office-of-finance
description: >-
  BUILDING BLOCK for a Sigma workbook / dashboard / POV tailored to an
  **Office of Finance** buyer (CFO, Controller, FP&A, Corporate Accounting)
  inside a named company or prospect — via the workbooks-as-code API
  (POST /v2/workbooks/spec). Encodes the finance-persona page set: FP&A
  BUDGET vs. ACTUAL & VARIANCE, FINANCIAL CLOSE / RECONCILIATION exception
  tracking, and a ROLLING FORECAST page (composes **sigma-input-table-app**'s
  verified linked-input-table + Δ/variance pattern rather than re-deriving
  it). Use this DIRECTLY when the ask is "build a finance dashboard / FP&A
  workbook / budget-vs-actual demo / close tracker / CFO POV for [company]".
  For the full multi-persona branded workbook (command center + scenario
  modeler + cohort builder + PDF report), use **sigma-company-dashboard-v2**
  instead — this skill is the finance-specific page set it can delegate to.
  Does NOT cover treasury/cash-management or capital-allocation modeling yet
  (flagged as a follow-up pattern, not built out) — say so rather than
  guessing if asked for it.
---

# Sigma Office of Finance — FP&A, Close, and Forecast pages

This is a **workbook-pattern skill** (see `docs/skill-authoring.md`) for the
finance-department persona, iterated off **sigma-company-dashboard-v2**'s
architecture and composing **sigma-input-table-app** for the forecast page.
It is scoped to the three patterns below; more Office-of-Finance patterns
(treasury/cash, capital allocation, tax) get added here as new reference
files + a page, not as a new skill — see "Adding a new pattern" at the
bottom.

## Read this first

1. **`reference/structure.md`** — the three canonical pages, required vs.
   optional elements on each, and how they relate to each other.
2. **`reference/kpis.md`** — canonical KPI definitions (formula, format,
   dependencies) for all three pages. Use `[Metrics/<Name>]` over
   hand-deriving these when a data model has them.
3. **`sql/`** — one exemplar query per page, following the
   `sigma-company-dashboard-v2/sql/*.sql` shape (synthetic-but-plausible
   trailing-window data, reusable across prospects by swapping the seed
   constants at the top of the file).

Defer to **sigma-workbook-conventions** for element naming/layout mechanics
and **sigma-data-models** for field-level mechanics — this skill only adds
the finance-domain structure on top.

## The pages

| # | Page | Pattern source | Status |
|---|------|-----------------|--------|
| 1 | FP&A Budget vs. Actual & Variance | new (this skill) | PUT + compile-verified 2026-08-24, restyled (`workbooks/office-of-finance/build_page1.py`); not yet visually verified or promoted to `examples/` |
| 2 | P&L Statement | new (this skill) | PUT + compile-verified 2026-08-24 (`build_pl.py`); not yet visually verified |
| 3 | General Ledger | new (this skill) | PUT + compile-verified 2026-08-24 (`build_gl.py`); not yet visually verified |
| 4 | Rolling Forecast — "the forecasting module" | linked-input-table pattern from `sigma-input-table-app` (now ported into this repo) | PUT + compile-verified 2026-08-24 (`build_forecast.py`); builds the core seeded-Base-Case + editable grid + comparative-KPI loop, not the full scenario create/submit/approve modal lifecycle; not yet visually verified |
| — | Financial Close / Reconciliation | new (this skill) | drafted in `reference/structure.md`, no build script yet — deprioritized in the 2026-08-24 build, see `workbooks/office-of-finance/notes.md` → "Open decisions" |

All 4 built pages live in **one** workbook (`workbookId
759ddb59-8b5c-4d80-a431-fe24773c483d`), assembled by
`workbooks/office-of-finance/build_workbook.py`. None of them have a
round-tripped `examples/exemplar-spec.json` yet — see `examples/README.md`.
Treat everything here as a strong first draft to POST, GET-back, visually
verify, and correct per the iteration playbook, not as pre-verified fact
the way `sigma-company-dashboard-v2`'s HANDOFF.md is (and note: this skill
deliberately does NOT reuse `sigma-company-dashboard-v2` — its brand/logo/
gradient system and 14 hardcoded companies turned out to be bank/lending-
specific, not reusable for P&L/GL/forecast pages; the aesthetic system here
comes from `sigma-input-table-app` instead — see `scripts/style.py`).

## Non-negotiable DEFAULTS — build these every time

1. **Variance is always signed and visually distinct.** Budget-vs-actual
   variance = `[Actual] - [Budget]`; color/format so over-budget on a cost
   line and under-budget on a revenue line both read as "bad" (don't just
   color positive green everywhere — it inverts for expense rows).
2. **Every reconciliation exception has an age.** `Days Open = TODAY() -
   [Exception Opened Date]`; surface an aged-exceptions KPI (e.g. `% Open
   Exceptions > 5 Business Days`) — a raw open-count without aging undersells
   how close-risk actually reads to a controller.
3. **Forecast page reuses the input-table-app Δ/variance + Coalesce(entry,
   baseline) defaults** — don't re-derive them. See
   `sigma-input-table-app/reference/scenario-modeler-pattern.md`.
4. **Titles name the fiscal period explicitly** (e.g. "Q3 FY26 Budget vs.
   Actual", not "Budget vs. Actual") — finance reviewers anchor on period
   before anything else.

## Adding a new Office-of-Finance pattern (treasury/cash, capital allocation, tax, etc.)

1. Add `reference/<pattern>.md` (structure) and extend `reference/kpis.md`
   with that pattern's KPI table.
2. Add `sql/<pattern>.sql`.
3. Build it once via the standard iteration playbook
   (`docs/iteration-playbook.md`), GET-back, visually verify, and only then
   drop the real spec into `examples/` and update the status table above.
4. Do not fork a new skill for this — extend this one, per
   `docs/skill-authoring.md`'s promotion rule ("pattern-specific" fixes live
   in `<pattern-skill>/reference/<topic>.md`).
