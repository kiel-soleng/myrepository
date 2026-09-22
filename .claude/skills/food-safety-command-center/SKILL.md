---
name: food-safety-command-center
description: >-
  Use when building a food-safety / quality-audit command center for a
  multi-location restaurant, grocery, or retail chain — trigger phrases like
  "food safety dashboard", "audit risk command center", "store compliance
  workbook", or "whitelabel/rebrand the [Chipotle] food safety workbook for
  [customer]". Encodes a known-good 7-page pattern (Executive Command
  Center, Risk & Response, Manager Report, Promo Scenario Modeler,
  Exploration, + 2 hidden data pages), 8 canonical risk/audit KPIs, 6 AI
  chat agents, and a corrective-action/attestation workflow, harvested from
  a real Chipotle-branded instance. Ships with an explicit branding token
  map (`reference/branding.md`) so company name, logo, background texture,
  and brand accent color can be swapped per customer while the page
  structure, KPI formulas, and AI-agent behavior stay fixed. Prerequisites:
  `sigma-api` (auth), `sigma-data-models` (field-level mechanics),
  `sigma-workbook-conventions` (spec-authoring conventions — read this
  skill's chunk-reading gate before drafting any plan). Does NOT cover
  recreating the Sigma "Report" (scheduled/pinned page export) linked from
  the Exec Report modal — that's a separate Sigma object type with no
  spec API, set up per customer after the workbook is published.
---

# Food Safety Command Center

A domain workbook-pattern skill (see `docs/skill-authoring.md`) for
multi-location food-safety / audit-risk dashboards, plus a **whitelabel
workflow**: the same structural pattern, re-skinned per customer.

Currently anchored on a single exemplar (the Chipotle instance below) rather
than the usual 2–3 — created early at explicit user request. Treat
`branding.md`'s token map as provisional until a second customer instance is
built and any gaps it exposes get folded back in.

## What's fixed vs. what's customer-specific

- **Fixed** (don't change without a real product reason): page structure,
  overlay/modal set, the 8 canonical KPI formulas and their current/prior
  pairing, the corrective-action/attestation workflow, AI-agent auto-query
  behavior. See `reference/structure.md` and `reference/kpis.md`.
- **Customer-specific** (change every time): company name (in AI agent
  personas, CallText prompts, static report text, compliance link),
  logo URL, decorative background texture, brand accent color, font family.
  See `reference/branding.md` for the exact field-by-field token map and a
  copy-pasteable checklist.

## Workflow for a new customer instance

1. Read `reference/structure.md` and `reference/kpis.md` — confirm the
   customer's use case actually matches this pattern (multi-location,
   audit/inspection-driven risk scoring, corrective-action tracking). If
   their data model doesn't have an analogous Audit/Task/Risk feed, this
   pattern needs adaptation, not blind copying.
2. Read `reference/branding.md` in full before touching the spec. Copy its
   "Customization checklist" into the build plan — per this repo's
   **HARD GATE** in `sigma-workbook-conventions` SKILL.md, plans need a
   `Chunks Read:` line naming the chunk files consulted.
3. Ask the user (don't guess) for: company name, logo URL, primary brand
   color (hex), font family (if their Sigma org has one licensed), and the
   customer's own compliance/SOP reference URL. Do not carry over Chipotle's
   `chipotle.com` URLs into another customer's workbook.
4. Start from `examples/chipotle-exemplar-spec.json` as the structural
   base. Remap data-model field references (`sigma-data-models`) to the
   new customer's actual tables/columns — the exemplar's `Audit Feed` /
   `Task Feed` / `Risk Feed` names are illustrative, not literal
   requirements.
5. Work the branding checklist top to bottom. Finish with a case-insensitive
   grep for the old company name across the new spec.json — zero
   unintended hits is the bar.
6. Follow the standard `sigma-workbook-conventions` POST/GET/visual-verify
   loop — plan approval is still the only authorization for the
   state-changing POST.

## Files

- `reference/structure.md` — canonical pages, overlays, AI agents, gotchas.
- `reference/kpis.md` — the 8 KPI formulas + current/prior pairing pattern.
- `reference/branding.md` — the whitelabel token map (colors, logo, company
  name locations, font, out-of-scope items) and the customization checklist.
- `examples/chipotle-exemplar-spec.json` — the harvested real spec (workbook
  id `981e67d6-5cc4-43dd-83b4-9d86a4fb87f4`, org `papercrane`).
- `examples/chipotle-exemplar-source.json` — harvest provenance (workbook
  id, name, harvest timestamp).
