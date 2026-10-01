---
name: sigma-workbook-planner
description: Use this skill whenever the user wants to build, create, or design a Sigma workbook or dashboard by describing it in prose, using the Sigma MCP server's plan/build tools — phrases like "build a Sigma workbook", "create a dashboard in Sigma", "make a Sigma report off [table/data model]". This is the MCP plan-based route (start_workbook_plan / build_workbook) — no spec.json authoring, no direct REST POST, no local .env credentials. If this project also has a spec.json-authoring skill (e.g. sigma-workbook-conventions) for hand-authoring raw workbook definitions via REST, that is a DIFFERENT lower-level workflow — use this skill instead whenever an MCP Sigma connector is configured and the user wants the faster plan-then-build path rather than full element-by-element control.
---

# Sigma Workbook Planner (Claude Code, MCP-native)

## What this is for

This skill drives Sigma's **plan-then-build** flow through Sigma's MCP server
tools (`search`, `describe`, `start_workbook_plan`, `build_workbook`, etc.),
assuming a Sigma MCP connector is already configured for this project. You
never author workbook JSON yourself — you write a markdown **plan**, the user
approves it in this session, and Sigma's own Builder agent constructs the
actual workbook from that plan when they open the returned URL.

**This is not the same workflow as hand-authoring `spec.json` and POSTing to
`/v2/workbooks/spec` directly.** If this repo has a project-local skill for
that (raw element specs, layout XML, `validate-spec.py`, local OAuth token
scripts), that skill exists for full element-by-element control and doesn't
need this one — and vice versa. Don't mix the two approaches in one workbook:
pick the plan/build route (this skill) or the direct-spec route, not both.

## Setup notes for this environment

- If the MCP session requires an explicit `begin_session` call, make that the
  first tool call of any Sigma-related task in this session — it returns
  workflow instructions and a starter set of recent/favorite/recommended
  documents that can save a discovery round-trip.
- No `.env`, no local credential bootstrapping — the MCP server owns auth.
  If a Sigma MCP tool call fails with an auth error, tell the user to
  reconnect the MCP server rather than trying to work around it with local
  scripts.

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
4. **Draft and iterate.** Write the plan body, show it to the user, and revise
   based on their feedback before moving on.
5. **Get explicit approval.** Do not call `build_workbook` speculatively.
   Wait for the user to actually approve the plan you showed them.
6. **Build.** Call `build_workbook({ plan: { title, summary, body, sources? },
   workbook_name })` exactly once. Render the returned URL as a clickable
   markdown link. Tell the user Builder will construct the workbook when they
   open it — further edits happen inside Sigma's editor, not in this session.

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
