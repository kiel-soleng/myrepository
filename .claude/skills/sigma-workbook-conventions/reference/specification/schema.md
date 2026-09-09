# Workbook spec — top-level schema

The overall shape of the workbook spec passed to `POST /v2/workbooks/spec`.

## Consulting the OpenAPI

**The old URL is dead.** `help.sigmacomputing.com/openapi/sigma-computing-public-rest-api.json`
404s. The live landing page (`https://help.sigmacomputing.com/openapi.json`,
itself an HTML picker, not JSON) lists two separate specs:

```bash
curl -sf https://help.sigmacomputing.com/openapi/sigma-rest-api.json > /tmp/sigma-api.json
curl -sf https://help.sigmacomputing.com/openapi/code-representation.json > /tmp/sigma-code-repr.json

# A specific element kind's full shape (sigma-rest-api.json covers most endpoints)
jq '.components.schemas.BarChart' /tmp/sigma-api.json
jq '.components.schemas.KpiChart' /tmp/sigma-api.json

# List every schema name (when you don't know the right one)
jq -r '.components.schemas | keys[]' /tmp/sigma-api.json | grep -i <hint>
```

**⚠️ Neither published OpenAPI file documents `POST /v2/workbooks/spec`
or its request/response shape.** `sigma-rest-api.json` has no `/spec`
paths at all; `code-representation.json` only covers
`/v2/dataModels/spec`. The workbook-spec endpoint's real schema is
**not publicly documented** — confirmed 2026-09-09 on a staging tenant,
where the actual shape (see "Top-level object" below) differs
substantially from what earlier revisions of this file assumed. When
you hit unexplained rejections here, don't waste time hunting for a
matching OpenAPI schema — go straight to the two fallbacks below.

### Schema-drift signal

If a POST/PUT fails with `invalid argument`, `unknown field`,
`unexpected property`, `missing required field`, `unrecognized parameter`,
or a 400 about request *shape* rather than data — the API has evolved
since this skill was written. Fallback in `reference/workflows/crud.md` →
"Schema drift."

**Fastest real fallback: GET an existing real workbook's spec** (one you
already have an id for, e.g. via `mcp-search.sh "" --types workbook` then
`publish-workbook.sh get-spec <id>`) and diff its shape against what
you're about to POST. This is how the 2026-09-09 drift below was
actually diagnosed — the error messages alone (especially the giant
union-type dump on a totally-wrong envelope) are far harder to parse
than just reading a known-good real example.

This file covers what the OpenAPI alone won't tell you: which fields are
response-only, the ID-preservation guarantee on CREATE, and a minimal
working example. For per-element shapes, see the per-element files in
this directory.

## Top-level object

> ⚠️ **2026-09-09 drift.** This section previously documented a flat
> `{name, folderId, schemaVersion, pages, layout}` body. **That shape is
> rejected** on the current API (confirmed on a staging tenant) with a
> multi-kilobyte union-type validation error whose root cause is: the
> workbook body must be wrapped in a `document` object, and `pages` no
> longer nests `elements` — see below. Verified by GET-ing several real
> production workbooks and comparing.

```json
{
  "name": "My Workbook",
  "folderId": "<folder-uuid>",
  "description": "Optional description",
  "document": {
    "schemaVersion": 1,
    "kind": "workbook",
    "pages": [
      { "id": "page-1", "name": "Overview" }
    ],
    "elements": [
      { "id": "sales-table", "kind": "table", "pageId": "page-1", "...": "..." }
    ],
    "layout": "<?xml version=\"1.0\" encoding=\"utf-8\"?>...</Page>..."
  }
}
```

**Required top-level:** `name`, `folderId`, `document`.
**Required inside `document`:** `schemaVersion`, `kind: "workbook"`,
`pages`, `elements`, `layout`.
**Optional:** top-level `description`; `document.settings`,
`document.agents`, `document.automatedActions` (newer features —
AI agents and automated actions embedded in the workbook; out of
scope for this skill until a verified pattern emerges).

### Pages are `{id, name}` only — elements are flat, with `pageId`

**Each page no longer carries an `elements` array.** Sending
`document.pages[].elements` is rejected outright with:

```
document.pages[].elements is no longer supported. Move elements to document.elements instead.
```

Instead: `document.elements` is **one flat array for the whole
workbook** (not per-page), and **every element must carry a
`pageId` field** naming which page it belongs to:

```json
{
  "document": {
    "pages": [
      { "id": "page-1", "name": "Overview" },
      { "id": "page-2", "name": "Detail" }
    ],
    "elements": [
      { "id": "kpi-a", "kind": "kpi-chart", "pageId": "page-1", "...": "..." },
      { "id": "tbl-a", "kind": "table",     "pageId": "page-2", "...": "..." }
    ]
  }
}
```

Element declaration order in the array does **not** need to match
dependency order — a KPI can appear before the table it sources from
(verified against real harvested workbooks where source tables are
declared near the end of a 150+ element array).

See `reference/history.md` → "2026-09-09 — Workbook-spec envelope
drift (document wrapper, flat elements, layout tag rename, Custom SQL
prefix)" for the full incident, including three more drifts (layout
XML tag names, unsupported chart kinds, `sql`-source column
resolution) found in the same session.

See `reference/workflows/crud.md` → "schemaVersion — don't hardcode"
for the rule on `schemaVersion`. Existing exemplars use `1`; future
versions will require reading from a reference GET.

## Response-only fields

`GET /v2/workbooks/<id>/spec` also returns these — they **must be
stripped** before using the spec as a CREATE or UPDATE body. Sending
unknown top-level fields is rejected:

- `workbookId`
- `url`
- `documentVersion`
- `latestDocumentVersion`
- `ownerId`
- `createdBy`
- `updatedBy`
- `createdAt`
- `updatedAt`

`scripts/workbook-manifest.py` recognizes these and won't flag them
as unknown. `scripts/validate-spec.py` warns when they're present on
a file being POSTed.

## Pages

`document.pages` is just the page list — `{id, name}` (see "Pages are
`{id, name}` only" above; `elements` moved out to `document.elements`
with a `pageId` back-reference, current API only):

```json
{ "id": "page-overview", "name": "Overview" }
```

Optional page-level keys:

- `visibility: "hidden"` — hides the page from the workbook's tab bar.
  See `reference/specification/text.md` and the iteration pattern in
  `reference/workflows/plan.md`.
- `description` — page-level description string.

`document.elements` holds tables, charts, KPIs, controls, containers,
text, dividers, and images — each tagged with the `pageId` it belongs
to. See the per-element reference files.

## ID rules

- Element IDs and column IDs must be **unique within their scope**
  (the same `id` on different pages is allowed; the same `id` twice
  in one page is not).
- Use descriptive kebab-case or short random-looking IDs — both are
  fine. IDs are internal identifiers, not displayed to users.
- **IDs are preserved verbatim on `POST`.** Pages, elements, and
  columns keep the `id` values you sent. Layout `elementId`
  references stay valid across POST/PUT round-trips. You can save a
  spec, edit it, and `PUT` it back directly using the same IDs.
- Layout `elementId` references must match an element `id` on that
  page exactly (case-sensitive).

Verified 2026-07-02 against harvested exemplars: skill-authored
workbooks (`plugs-geography-yoy`, `store-performance-pop`) retained
100% of their kebab-case IDs after POST/GET round-trip.

## Layout

`layout` is a top-level XML string carrying one `<Page>` element per
workbook page. Multi-page workbooks concatenate the per-page XML docs
(each with its own `<?xml ?>` declaration). See
`reference/specification/layout.md`.

## Top-level `folders` field

Optional. Carries column-folder groupings for the workbook. Most
workbooks omit it. When present, looks like:

```json
"folders": [
  { "id": "ejtrqOFhcK", "name": "Store Fields", "items": [...] }
]
```

The `items` are column IDs grouped under the folder name. UI-side
organization; doesn't affect render. Inspect via `mcp-describe.sh
workbook <wb-id>` if you need the structure.

## Top-level `themeOverrides` field — REMOVED, use `document.settings.theme.overrides`

> ⚠️ **2026-09-09 drift.** `document.themeOverrides` (or top-level
> `themeOverrides`) is rejected outright:
> `document.themeOverrides is no longer supported. Use document.settings.theme.overrides instead.`
> The replacement is a much richer object than the old
> `{pageWidth, space}` pair — verified against real harvested workbooks:
>
> ```json
> "settings": {
>   "theme": {
>     "overrides": {
>       "colors": { "text": "#0b2740", "highlight": "#0074f5", "success": "#0ea5a0", "warning": "#e1a32d", "danger": "#ef4444", "darkMode": "hidden" },
>       "colorOverrides": [ { "name": "backgroundCanvas", "color": "#eef2f7" }, { "name": "canvasBackground", "color": "#eef2f7" } ],
>       "categoricalScheme": ["#0074f5", "#00c4a7", "#0b2740", "#03aaff", "#00a2c7", "#7cc7e8", "#4a90e2", "#0a4e8b"],
>       "fonts": { "textFont": "Inter", "dataFont": "Inter" },
>       "borderRadius": "round",
>       "space": { "unit": "small", "showElementPadding": "shown" }
>     }
>   }
> }
> ```
>
> No confirmed field for `pageWidth` specifically was found in this
> session — treat as an open question. Not essential to most builds;
> safest to omit `settings` entirely unless the user asks for
> workbook-wide theme overrides.

## `theme` element kind

A named theme reference that can appear inside `pages[].elements[]`
alongside data-viz elements:

```json
{
  "kind": "theme",
  "ref": "colors-textNeutral"
}
```

Observed in `sales-mbr-sentinel` (2 instances). Applies theme-level
styling by reference. Inspect the OpenAPI for the enum of valid `ref`
values before authoring. Kept minimal here until a fuller pattern
emerges.

## Minimal working example

The smallest spec that creates a workable workbook, in the current
document-wrapped, flat-elements shape (verified 2026-09-09):

```json
{
  "name": "Sales Dashboard",
  "folderId": "<folder-uuid>",
  "document": {
    "schemaVersion": 1,
    "kind": "workbook",
    "pages": [
      { "id": "page-1", "name": "Overview" }
    ],
    "elements": [
      {
        "id": "sales-table",
        "kind": "table",
        "name": "Sales Data",
        "pageId": "page-1",
        "source": {
          "kind": "warehouse-table",
          "connectionId": "<conn-uuid>",
          "path": ["SALES_DB", "PUBLIC", "ORDERS"]
        },
        "columns": [
          { "id": "col-order-id", "name": "Order ID", "formula": "[ORDERS/order_id]" },
          { "id": "col-amount",   "name": "Amount",   "formula": "[ORDERS/amount]" },
          { "id": "col-total",    "name": "Total",    "formula": "Sum([Amount])" }
        ]
      }
    ],
    "layout": "<?xml version=\"1.0\" encoding=\"utf-8\"?><Page type=\"grid\" gridTemplateColumns=\"repeat(24, 1fr)\" gridTemplateRows=\"auto\" id=\"page-1\"><Element elementId=\"sales-table\" gridColumn=\"1 / 25\" gridRow=\"1 / 10\"/></Page>"
  }
}
```

Notes:

- `[ORDERS/order_id]` references a warehouse column (table prefix required).
- `Sum([Amount])` references the "Amount" column defined in the same
  element (no prefix).
- `<Element>` is the current layout tag name (was `<LayoutElement>` —
  see `layout.md` → "2026-09-09 drift").
- For a `kind: "sql"` source instead of `warehouse-table`, see
  `sources.md` → "sql" for the `Custom SQL` column-prefix rule — it
  does **not** follow the same-name-as-element convention other
  source kinds use.

For a realistic multi-page reference, see
`examples/data-model-sourced-multi-page-profitability-attrition.json`.
For a full official multi-page example, see `example-full.yaml` in
this directory.
