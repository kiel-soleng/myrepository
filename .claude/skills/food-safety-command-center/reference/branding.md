# Branding / whitelabel token map

Everything in this file is what changes per customer. `structure.md` and
`kpis.md` are what stays constant. When adapting the exemplar
(`examples/chipotle-exemplar-spec.json`) for a new customer, work through
every row below — missing one leaves a stray "Chipotle" or the wrong red in
the shipped workbook.

There are two different substitution mechanisms in this spec. Use the right
one for each token — don't hardcode a hex where a theme ref already exists,
and don't expect a theme ref to fix inline text spans (it won't).

## 1. Theme-level colors (`document.settings.theme`) — easy, do this first

```json
"theme": {
  "name": "831f0331-e7c3-4578-bc03-043530a04a77",
  "overrides": {
    "colors": {
      "text": "#171717",
      "highlight": "#3c405b",
      "surface": "#d4d4d4",
      "success": "#46a758",
      "warning": "#ee8a2b",
      "danger": "#d94021",
      "darkMode": "hidden"
    },
    "colorOverrides": [{ "name": "backgroundCanvas", "color": "#f7f7f7" }],
    "pageWidth": "large"
  }
}
```

- `success` / `warning` / `danger` are **semantic status colors** (risk
  tiers, pass/fail, on-track/overdue). Keep these close to standard
  green/amber/red regardless of brand — recoloring them to match a brand
  palette makes the dashboard harder to read, not more on-brand. Only shift
  them if the customer's brand red/green would otherwise clash badly.
- `highlight` is the one color here that's safe to set to the customer's
  primary brand color.
- `theme.name` references an org-level theme by ID — it won't resolve for a
  different org/customer. Either omit it and rely purely on `overrides`, or
  look up (or create) an equivalent theme in the target org first.

## 2. Inline hex colors in text/KPI elements — tedious, do this second

The exemplar does **not** exclusively use theme refs — many `text` and
`kpi-chart` elements hardcode brand color directly in the element body as
inline HTML spans or `name.color` fields, e.g.:

```
<span style="color: #a81712">**FOOD SAFETY & RISK REPORT**</span>
```
```json
"name": { "text": "AUDIT PASS RATE", "color": "#a81712", "fontSize": 15 }
```

Brand-accent hexes to find-and-replace throughout `spec.json` (search for
these literal strings — grep for the hex, not just "Chipotle"):

| Hex | Usage | Swap to |
|---|---|---|
| `#c24a38`, `#a81712`, `#a81612`, `#ac2219`, `#ac2318`, `#ac2218`, `#441400`, `#441503`, `#461400` | Brand-red family — KPI titles, section headers, callout emphasis spans | Customer's primary brand color (and 2–3 tint/shade variants if the design needs emphasis levels) |
| `#5e6921`, `#a9cc8f`, `#cdebb8` | Secondary brand-green family — used decoratively (not as a status color) | Customer's secondary brand color, or drop if the customer has no secondary color |
| `#717171`, `#333333`, `#515151`, `#171717`, `#b4b4b4`, `#d4d4d4` | Neutral grays — body text, muted labels | Usually leave as-is; these aren't brand-specific |
| `#e8a597`, `#f7f2ed`, `#fefefe`, `#fffbfa` | Light brand tints (backgrounds, subtle fills) | Light tint of the customer's primary color |
| `#b68208` | Amber — check whether it's semantic (warning-adjacent) or decorative before touching |

Do **not** touch colors that map to risk tiers / pass-fail / status
(reds/greens/ambers used in the scatter chart, region map, or repeated-
container conditional formatting) — those must stay semantically red =
bad, green = good, independent of brand.

## 3. Company name — hardest, needs manual review per hit, not blind find/replace

"Chipotle" appears 32 times across the spec. It is **not** a single field —
find/replacing the literal string "Chipotle" will miss context and can
break formulas. Known locations in the exemplar:

- **AI agent instructions** (`document.agents[].instructions`) — 3 of 6
  agents name the company directly in their persona line, e.g. *"You are a
  Risk Intelligence Advisor for Chipotle restaurant operations..."* Rewrite
  the persona sentence per agent; don't just swap the word.
- **AI-narrative `CallText(...)` formulas** embedded in `text` element
  bodies (Executive Command Center, Manager Report) — the prompt string
  itself says *"You are a food-safety operations analyst for Chipotle."*
  This is formula text, so edit it as a formula, not as display text.
- **Static header/report text** — e.g. the Manager Report page header
  (`**Restaurant R0002 — Chipotle #1002**`) and the attestation disclaimer
  (*"...in accordance with Chipotle food-safety standard operating
  procedures..."*). Plain text spans — safe to find/replace within the
  element body.
- **External link text + URL** — `[Chipotle Food Safety Standards and
  Procedures](https://www.chipotle.com/food-safety "...")`. Needs the
  customer's own compliance/SOP reference — ask the user for this URL; do
  not invent one, and do not leave the Chipotle URL live in another
  customer's workbook.
- **Store naming convention** (`Chipotle #1002`) — cosmetic label pattern
  used in sample/static text only; the underlying data model uses
  `Restaurant Id` (e.g. `R0002`), not a Chipotle-specific ID scheme. Rename
  the display label to match the customer's own store-naming convention if
  they have one (e.g. "Store #4021" vs. "Location 4021").

**Workflow:** grep the target spec.json for `chipotle` (case-insensitive)
after every edit pass until it returns zero hits *outside* of URLs/asset
paths you've intentionally deferred (see §5). Zero stray mentions is the
bar — not "most of them."

## 4. Logo and decorative imagery

| Element | Field | Chipotle asset | Action |
|---|---|---|---|
| `xc-logo` | `source.url` | `chipotle.com/.../cmg-medallion-logo.svg` | Replace with customer's logo URL (must be a publicly reachable image URL — Sigma renders it as an `<img src>`, no auth) |
| 6 elements with `backgroundImage.source.url` (`ug36f8WhFL`, `CafGDFhOFO`, `ymFZTtQ1D4`, `3UJGdXWX9D`, `0Jp3vChmAM`, `XVexK_rOb4`) | `backgroundImage.source.url` | `chipotle.com/.../pattern-ingredients.svg` — a decorative background texture, not a logo | Either replace with a customer-brand texture/pattern, or delete the `backgroundImage` key and let it fall back to `backgroundColor` — decorative texture is optional, don't force a customer to have one |

## 5. The companion "Risk Profile Report" — a second, real exemplar

Correction to an earlier pass at this file: the Exec Report Modal's embed
is a Sigma **Report** object, a resource type distinct from workbooks —
but it is NOT opaque via the API. `GET /v2/workbooks/{id}/spec` 400s on a
reportId (`"does not belong to a workbook"`) because that's the wrong
endpoint, not because Reports lack one — the right endpoint is
`GET /v2/reports/{reportId}/spec`, which returns a full `document` (same
shape as a workbook: `elements`, `pages`, `layout`, `settings`), harvested
here as `examples/chipotle-risk-profile-report-spec.json` (58 elements, 3
pages: one visible `Report 1` page sized to US letter at 96dpi —
`config.pageWidth: 816, pageHeight: 1056` — plus 2 hidden pages). Its
schedule (cron, PDF export format, dynamic email title/body formula) is
also readable via `GET /v2/reports/{reportId}/schedules`, harvested as
`examples/chipotle-risk-profile-report-schedule.json`. Sigma also documents
`POST /v2/reports` (create, with an optional beta `contents` param) and an
"update a report from a code representation" beta endpoint for publishing
— exact PUT/POST path and payload shape for updating an existing report's
spec should be confirmed against `sigma-data-models`/live docs at build
time rather than assumed from this note.

This report is simpler to rebrand than the main workbook — no AI agents,
no `CallText` formulas, no `chipotle.com` mentions in body text. Its
branding surface is just:

| Token | Location | Action |
|---|---|---|
| Report `name` (top-level metadata, "Chipotle Risk Profile Report") | `source.json`-equivalent metadata, set at `POST /v2/reports` creation time | Set to the customer's own report name |
| Logo image | one `image` element, `source.url` = `https://www.preparedfoods.com/.../Chipotle_Logo_900.jpg` (a *different* logo asset than the main workbook's `xc-logo`) | Replace with customer's logo URL |
| Brand-accent hex `#a91513` (5 hits) | text/KPI-title color spans, same brand-red role as `#a81712` in the main workbook | Customer primary color |
| `#59A14E`/`#59a14e` (green), `#e15658` (red) | gauge-chart color stops | **Semantic** (good/bad) — leave as-is, same rule as §2 |
| `#e2e2e2`, `#898989` | neutral grays | Leave as-is |
| `document.settings.theme.overrides.fonts.textFont` / `.dataFont` = `"Gotham"` | theme-level font override (this report sets font at the theme level, unlike the main workbook's inline spans) | See font-family note below |

Rebrand this exemplar as its own pass — don't assume fixing the main
workbook's branding also fixes this file; they're two independent specs
with two independent asset URLs and two slightly different brand-red
hexes.

## 6. Font family (`Gotham`)

Both specs use Gotham (inline spans in the main workbook; a theme-level
`fonts` override in the Risk Profile Report). Gotham is Chipotle's brand
font and may not be licensed/available for another customer's Sigma org.
Ask the user what font (if any) their org has configured before carrying
this over — falling back to the theme default font is safer than assuming
Gotham renders.

## Customization checklist (copy into the build plan)

- [ ] `document.settings.theme.overrides.colors.highlight` → customer primary
- [ ] Confirm `success` / `warning` / `danger` stay semantic (don't rebrand)
- [ ] Grep + replace brand-accent hex family (§2 table)
- [ ] Rewrite 3 branded AI agent persona lines (§3)
- [ ] Rewrite 2 `CallText(...)` prompt strings naming the company (§3)
- [ ] Replace static header/report/attestation text mentioning the company (§3)
- [ ] Replace compliance/SOP link text + URL (§3) — ask user for the real URL
- [ ] Replace `xc-logo` image URL (§4)
- [ ] Replace or remove the 6 `backgroundImage` decorative texture URLs (§4)
- [ ] Rebrand `chipotle-risk-profile-report-spec.json` as its own pass:
      report `name`, its separate logo image URL, and its `#a91513`
      brand-red hex (§5)
- [ ] Recreate the report's schedule (cron, PDF export format, dynamic
      title/body formula) via `POST /v2/reports` + the report-spec/
      schedules endpoints, pointed at the customer's data — confirm exact
      publish payload shape at build time (§5)
- [ ] Confirm font-family choice with the user for both specs, don't
      default to Gotham (§6)
- [ ] Final grep for `chipotle` (case-insensitive) across **both** specs →
      zero unintended hits
