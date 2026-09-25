# Canonical KPIs — Food Safety Command Center

8 unique metrics, each appearing on the Executive Command Center (4 of them
also drive Risk & Response). Formulas are Sigma function syntax, taken
verbatim from the exemplar. Column/table names are the exemplar's data
model — remap to the customer's actual field names, but keep the same
logical definition (period comparison, tier bucketing, rate-of-X-over-Y).

| KPI | Formula | Format | Depends on |
|---|---|---|---|
| Audit Pass Rate | `Count(If([Audit Feed/Period Name] = "Current Month" and [Audit Feed/Pass Fail] = "Pass", [Audit Feed/Audit Id], Null)) / Count(If([Audit Feed/Period Name] = "Current Month", [Audit Feed/Audit Id], Null))` | percent | `Audit Feed` (Period Name, Pass Fail, Audit Id) |
| Avg Risk Score | `Avg(If([Risk Feed/Period Name] = "Current Week", [Risk Feed/Weekly Risk Score], Null))` | number, `.0f` | `Risk Feed` (Period Name, Weekly Risk Score) |
| Task Completion | `Count(If([Task Feed/Period Name] = "Current Month" and [Task Feed/Task Status] = "Done", [Task Feed/Completion Id], Null)) / Count(If([Task Feed/Period Name] = "Current Month", [Task Feed/Completion Id], Null))` | percent | `Task Feed` (Period Name, Task Status, Completion Id) |
| High-Risk Stores | `CountDistinct(If([Risk Feed/Period Name] = "Current Week" and In([Risk Feed/Risk Tier], "High", "Critical"), [Risk Feed/Restaurant Id], Null))` | number, `,.0f` | `Risk Feed` (Period Name, Risk Tier, Restaurant Id) |
| Task Miss Rate | `[Task Feed/Task Miss Rate Current Month]` (precomputed column) | percent | `Task Feed` |
| Audit Failure Rate | `[Audit Feed/Audit Fail Rate Current Month]` (precomputed column) | percent | `Audit Feed` |
| Danger Zone | `[FOOD_SAFETY_AUDITS/Danger Zone Stores]` (precomputed column) | number | `FOOD_SAFETY_AUDITS` |
| Risk Trend | `[Risk Feed/Risk Trend Current Week]` (precomputed column) | number/sparkline | `Risk Feed` |

## Pattern notes

- **Current/prior pairing — correction.** The "hidden prior twin" is NOT a
  top-level `visibility: hidden` on a second element. In the harvested
  exemplar, the prior-period element's `name.visibility` is `"hidden"`
  (only its title label is suppressed) and the CURRENT element already
  carries its own `comparisonColumn` pointing at a sibling column *on
  itself* (e.g. `k-passc`'s `k-passcc` column, formula scoped to `"Prior
  Month"`) — the delta arrow does not need the twin element at all. The
  twin elements were laid out overlapping/adjacent to the current tile
  inside a `type="stack"` sub-container (see next point), which is why
  they read as "hidden" — they were a secondary, rarely-visible surface
  (e.g. a toggle), not the trend-arrow data source. **When rebuilding this
  pattern, the current-only element with its own `comparisonColumn` is
  sufficient** — treat the prior twin as optional, not required.
- **KPI row lost entirely if the workbook was cloned/rebranded before this
  was known: root cause and recovery.** The Executive Command Center's KPI
  row lives inside a `type="stack"` layout container (see
  `sigma-workbook-conventions/reference/scope-and-edge-cases.md` →
  `type="stack"` layout containers). GET-spec serializes `type="stack"` as
  an empty stub with zero children — it never emits what's nested inside.
  If a workbook is harvested, its KPI *elements* still exist intact in
  `elements[]` (only their layout placement is lost) — but if a later
  POST/PUT cycle's placement validator then rejects those now-unplaced
  elements, a naive fix is to delete them from `elements[]` to get a clean
  POST, which silently and permanently loses the KPI tiles from that point
  forward (they won't be in the next GET-spec either). Symptom: the whole
  KPI row renders as a blank strip, with no error anywhere in the spec or
  compiled SQL — because the elements are simply gone, not broken.
  **Recovery, if you still have an untouched harvest of the same
  workbook/pattern:** diff the harvest's `elements[]` against the live
  spec's `elements[]` by id — any `kind: "kpi-chart"` element present in
  the harvest and absent live is a casualty of this bug. Re-add it,
  remapping its bare `[Table/Column]` formula references to the
  customer's renamed tables/columns (same names carry over if you kept the
  data model's display names during rebrand). Re-place it by converting
  the containing `type="stack"` container to `type="grid"` (drop the
  stack behavior entirely — no fix exists for stack, per
  scope-and-edge-cases.md) and adding ordinary `<Element gridColumn=...
  gridRow=.../>` children.
- **`comparison.display` without a `comparisonColumn` fails at PUT time**
  with `elements[N].comparison.display: requires a comparison column or
  period comparison on the KPI.` — if a KPI has no natural prior-period
  variant to diff against (e.g. Danger Zone Stores, which has no
  period-scoped formula), drop the whole `comparison` block rather than
  leaving a `display` config with nothing to compare.
- **Risk Tier bucketing** (`Critical` / `High` / `Medium` / `Low`, or
  equivalent) is the organizing dimension across nearly every page — the
  scatter chart, bar chart, region map, and repeated-container all filter or
  color by it. Preserve the tier vocabulary (or remap consistently) rather
  than inventing new bucket names per customer.
- **Miss-rate threshold `>= 0.3`** (30% task-miss rate) appears inline in
  the AI-narrative CallText formula (see `branding.md`) as a hardcoded
  business rule, not a config value. If the customer's operational
  threshold differs, this needs to change in the formula text, not just the
  underlying data.
- **Danger Zone's dependency chain is fragile — expect it to need its own
  fix pass.** `[FOOD_SAFETY_AUDITS/Danger Zone Stores]` depends on a
  sibling `Miss Task Rate` column that `Lookup()`s into a *separate*
  warehouse-table element (`TASK_COMPLETIONS` in the exemplar). Both of
  those source tables are easy to miss during a rebrand's data-reseeding
  pass because they're not the same elements as the page-level `Task
  Feed`/`Audit Feed` — grep the whole spec for every element whose
  `source.kind` is still `"warehouse-table"` pointed at the old
  connection's schema, not just the ones directly wired to visible charts.
  A stale source here fails the *whole* Danger Zone KPI (and any other
  chart sharing that table, e.g. a scatter chart plotting Miss Task Rate)
  even though nothing about the KPI element itself looks wrong.
