---
name: sigma-workbook-planner
description: Use this skill whenever the user wants to build, create, or design a Sigma workbook or dashboard through chat — phrases like "build a Sigma workbook", "create a dashboard in Sigma", "make me a Sigma report off [table/data model]", or any request to visualize warehouse/data-model data as a Sigma workbook. Also trigger if the user names a Sigma data model, table, or connection and asks for charts, KPIs, or a dashboard from it. This skill governs how to discover sources, ground a plan in real column/metric names, and hand that plan to Sigma's Builder agent via the Sigma MCP connector — do NOT author raw workbook JSON/spec files with this skill; that's a different, lower-level workflow. Make sure to reach for this skill even if the user's phrasing is casual, e.g. "can you throw together a sales overview in Sigma."
---

# Sigma Workbook Planner (chat / Cowork)

## What this is for

This skill drives Sigma's **plan-then-build** flow through the Sigma MCP
connector, available right in this chat. You never author workbook JSON — you
write a markdown **plan**, the user approves it, and Sigma's own Builder agent
constructs the actual workbook from that plan.

This is a different, higher-level tool than teams may have for authoring raw
`spec.json` workbook definitions via direct REST calls (a Claude Code–specific
workflow with its own local scripts and credentials). If the user is asking you
to hand-author element specs, JSON layout XML, or POST to a workbook API
directly, that's out of scope here — use whatever REST-based skill/tooling they
already have for that instead.

## The workflow, in order

1. **Discover.** Use `search` / `list_documents` to find the tables, data
   models, or data-model elements the user is talking about. See
   `reference/discovery.md` for when to use which.
2. **Ground.** Call `describe` on every source you're about to reference in the
   plan. Never write a column or metric name into a plan that didn't come from
   `describe` output or the user's own words.
3. **Start the plan.** Call `start_workbook_plan` (optionally with a one-line
   `goal`). This returns the authoritative `PLAN_STRUCTURE` template — five
   required markdown sections, in this exact order: **Goal, Decisions, Existing
   State, Build Outline, Layout**. Follow that template exactly; don't
   improvise different section names.
4. **Draft and iterate.** Write the plan body, show it to the user in chat, and
   revise based on their feedback. Treat this like any other collaborative
   draft — multiple rounds are normal and expected.
5. **Get explicit approval.** Do not call `build_workbook` speculatively or
   preemptively. Wait for the user to actually say yes to the plan you showed
   them.
6. **Build.** Call `build_workbook({ plan: { title, summary, body, sources? },
   workbook_name })` exactly once. Render the returned URL as a clickable
   markdown link. Tell the user Builder will construct the workbook when they
   open it — further edits happen inside Sigma's editor, not back in this
   chat.

See `reference/plan-examples.md` for three full worked examples (single-page
KPI dashboard, multi-page dashboard, ad-hoc chart off a raw table) showing the
difference between a vague plan and one Builder can actually execute well.

## Hard rules

- **Never invent identifiers, column names, or metric names.** Everything in
  the plan traces back to a `search`/`describe` call or the user's own words.
- **All five PLAN_STRUCTURE sections are required**, even when a section's
  content is short (e.g. "Existing State" is almost always just "Empty
  workbook" — `build_workbook` always creates a fresh workbook with one empty
  page).
- **`sources` is optional but capped at 5 entries.** Only list inodes the plan
  actually references in Build Outline/Layout. `datamodel-element` entries
  require both `inodeId` (the parent data model) and `nodeId` (the element —
  the same id you passed to `describe`).
- **One `build_workbook` call per workbook, after explicit approval.** There is
  no follow-up call to amend a plan once submitted — if the user wants changes
  after seeing the built workbook, that happens in Sigma's editor, or you draft
  and build a new plan.
- **Surface ambiguity, don't resolve it silently.** Two data models with
  similar names, an unclear folder, a column that could mean two things — ask,
  don't guess. See `reference/discovery.md`.

## Reference files

- `reference/discovery.md` — when to use `search` vs. `list_documents` vs.
  `describe`, and how to handle ambiguous matches.
- `reference/plan-examples.md` — three worked prompt → plan examples covering
  a single-page KPI dashboard, a multi-page dashboard, and an ad-hoc chart off
  a raw warehouse table.
