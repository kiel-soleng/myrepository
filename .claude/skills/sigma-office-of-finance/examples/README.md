# Examples — not yet populated

No `exemplar-spec.json` exists for this skill yet. Per
`docs/skill-authoring.md` step 5, one should be dropped in here after the
first real build:

```bash
GET /v2/workbooks/{workbookId}/spec   (Accept: application/json)
```

Do this the first time any of the three pages in `reference/structure.md`
gets built end-to-end (POST → GET-back → visually verified per
`docs/iteration-playbook.md`), then:

1. Save the verified spec as `exemplar-<page>-<shape>.json` (e.g.
   `exemplar-budget-variance-kpi-table-chart.json`).
2. Update the status column in `SKILL.md`'s page table from "drafted, not
   yet exemplar-verified" to a link to the exemplar.
3. If the build surfaced a fix that will recur, promote it into
   `reference/structure.md` or `reference/kpis.md` per the promotion rule.
