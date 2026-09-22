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

- **Current/prior pairing.** Audit Pass Rate, Avg Risk Score, Task
  Completion, and High-Risk Stores each have a twin KPI element scoped to
  `"Prior Month"` / `"Prior Week"` instead of `"Current Month"` / `"Current
  Week"`, set to `visibility: hidden`. The visible KPI's trend arrow reads
  the hidden twin's value. Reproduce both elements when porting a metric —
  a lone "current" KPI has no trend indicator.
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
