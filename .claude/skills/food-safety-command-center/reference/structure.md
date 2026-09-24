# Canonical structure — Food Safety Command Center

Harvested from a real workbook (Chipotle instance, `examples/chipotle-exemplar-spec.json`,
workbook id `981e67d6-5cc4-43dd-83b4-9d86a4fb87f4`, org `papercrane`). 308 elements
across 7 pages + 10 overlays (6 modals, 1 popover pair, 1 drawer) + 6 AI agents.

This is the skeleton every instance of this pattern should keep. See
`branding.md` for what to swap per customer; everything else below is a
structural default — deviate only if the customer's use case genuinely needs
a different page or metric, not for cosmetic reasons.

## Pages

| Page | Purpose | Key elements |
|---|---|---|
| **Executive Command Center** | Landing page. Network-wide risk posture at a glance. | KPI row (Audit Pass Rate, Avg Risk Score, Task Completion, High-Risk Stores — each with a hidden prior-period pair for trend deltas), region map (risk by state/geo), line chart (risk trend), table (store leaderboard), value-list (alerts), repeated-container (ranked risk-driver cards), AI-narrative text block (see below) |
| **Risk & Response** | Action queue for district/ops managers. | Scatter chart (risk vs. task-miss rate by store), bar chart (risk drivers), repeated-container (action items), chat element (Risk Intelligence Advisor agent), value-list |
| **Manager Report** | Single-store, print-style report for a store GM. | Header text block (store/GM/date — currently **static**, see gotcha below), 2 tables (audit + task detail), line chart, chat (Food Safety Analyst agent) |
| **Promo Scenario Modeler** | "What-if" tool: does a promo affect food-safety task load? | 9 controls (Active scenario, Discount %, Segment, Promo Start/End, Promo Channel, Item, Selected Scenarios), tabbed-container, waterfall + bar + 2 line charts, chat (Promo Scenario Assistant/Analyst agents) |
| **Exploration** | Freeform ad-hoc table for power users. | Single table, unrestricted |
| **Data Model** (hidden) | Backing tables + input-tables + controls consumed by every visible page. Not shown in nav. | 26 tables (Audit Feed, Task Feed, Risk Snapshots, Audit Records, Task Records, Store Risk Detail, …), 8 input-tables (open action log, completion log, scenarios, risk report profile), 20 controls |
| **Data for Manager Report** (hidden) | Input-tables specific to the Manager Report / corrective-action workflow. | Temperature logs, corrective actions |

## Overlays (modals/popover/drawer)

| Overlay | Type | Purpose |
|---|---|---|
| Exec Report Modal | modal | Embeds the linked store-level report (see branding.md — cross-workbook link) |
| Store AI Modal | modal | Full-screen chat with Risk Intelligence Advisor |
| Acknowledgement Modal for Open Items | modal | GM acknowledges an open risk/action item |
| Re-Open Modal for In Progress Items | modal | Re-open a closed corrective action with justification |
| Completion for In Progress Items | modal | Mark corrective action complete: root cause, resolution notes, photo evidence upload, attestation checkbox |
| Notification Details Modal | modal | Drill into a single alert |
| Evidence Modal | modal | View uploaded photo evidence |
| New Scenario Popover | popover | Create a promo scenario |
| Detail Data Drawer | drawer | Row-level detail slide-out |
| Scenario Comparison AI | popover | Chat comparing two promo scenarios |

## AI agents (6)

| Agent | Page/surface | Chipotle-specific? |
|---|---|---|
| Risk Intelligence Advisor | Store AI Modal / Risk & Response chat | Yes — persona line names the company |
| Food Safety Analyst | Manager Report chat | No — generic |
| Promo Scenario Assistant | Promo Scenario Modeler chat | Yes |
| Food Safety Risk Analyst | (secondary risk chat) | Yes |
| Promo Scenario Analyst | Promo Scenario Modeler chat | No |
| Store Manager Risk Advisor | (secondary manager chat) | No |

Agents also drive auto-query behavior on open (e.g. immediately querying
`@dataSource(...)` tables for the selected restaurant without asking) — keep
this behavior; only the company name in the persona/instructions text changes.

## Canonical KPIs

See `kpis.md` for the full formula table. The 4 headline KPIs (Audit Pass
Rate, Avg Risk Score, Task Completion, High-Risk Stores) each ship as a
**current/prior pair** — the prior-period KPI element is `visibility: hidden`
and exists only so the visible KPI's trend arrow can diff against it. Keep
this pairing pattern when adapting the metrics to a new customer's fields.

## Known gotchas (carried over from the exemplar — flag, don't silently fix)

- **Input tables in the "Data Model" / "Data for Manager Report" hidden
  pages come through harvest empty.** Sigma has no REST write path for
  input-table rows — a harvested-and-republished instance is
  structurally correct but has zero rows in every input table that had
  manually-seeded demo data (temperature logs, corrective actions,
  completion/attestation logs, scenario tables, risk report profiles).
  This is the dominant cause of "No data" showing up across a
  rebranded instance's pages. See `reference/data-seeding.md` for the
  fix (browser-automation CSV upload) and a hard warning about
  `Ctrl+A` inside an input-table's grid.
- **Manager Report header is static text, not formula-bound.** The header
  reads `General Manager: M. Alvarez · Monday, August 17, 2026` as a literal
  string, not driven by the selected-restaurant control. When adapting this
  pattern, either keep it static (and treat it as a "sample report" page) or
  upgrade it to a formula/control-bound text element — don't assume it's
  already dynamic.
- **GET-spec 500s** on some UI features (pivot conditional formatting; maps
  and color-by are suspected). If you re-harvest this workbook or a
  derivative and get a `service_error`, see
  `sigma-workbook-conventions/reference/scope-and-edge-cases.md`.
- **The Exec Report Modal embeds a Sigma "Report" resource**, not a second
  workbook. Reports are a distinct resource type with their own spec API —
  `GET /v2/reports/{reportId}/spec` (not `/v2/workbooks/.../spec`) — and
  their own schedule API (`GET /v2/reports/{reportId}/schedules`, cron +
  PDF export format + dynamic title formula). Harvested as a second
  exemplar: `examples/chipotle-risk-profile-report-spec.json` (58 elements,
  a single-page US-letter print layout: KPIs, tables, a gauge-chart, no AI
  agents) and `examples/chipotle-risk-profile-report-schedule.json`. See
  `branding.md` §5 for its own (smaller) branding token set — it has a
  different logo asset and a slightly different brand-red hex than the
  main workbook, so rebrand it as its own pass, not as a byproduct of
  rebranding the workbook.
