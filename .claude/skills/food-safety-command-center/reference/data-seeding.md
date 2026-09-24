# Seeding customer data after a rebrand

Rebranding the spec (branding.md) only changes labels and colors. It does
**not** give the new customer real data. This doc covers the two distinct
data problems every rebrand hits, and the browser-automation recipe that
fixes both. Read this before telling a user a rebrand is "done."

## The two problems

1. **Warehouse-backed tables carry the old customer's rows.** `RESTAURANTS`,
   `RISK_SCORES`, `FOOD_SAFETY_AUDITS`, `ACTION_ITEMS`, `ACTION_LOG`,
   `TASKS`, `TASK_COMPLETIONS`, `EMPLOYEES` (or your customer's equivalent
   Custom-SQL/warehouse-table sources) resolve to whatever restaurant chain
   the exemplar was harvested from. A rebrand that only touches labels
   leaves every store name, address, and score literally showing the old
   brand.
2. **Input tables (`kind: "empty"` or `"linked"`) come across empty.**
   Sigma has **no REST write endpoint for input-table row data** — GET/PUT
   `/v2/workbooks/.../spec` round-trips structure only. Any input table
   that had manually-seeded demo rows in the exemplar (temperature logs,
   corrective actions, completion/attestation logs, scenario tables, risk
   report profiles) comes through harvest-and-republish as **structurally
   correct but zero rows**. This is the dominant cause of "why is half the
   dashboard showing 'No data'" after an otherwise-successful rebrand —
   distinct from and larger than any branding/formula bug. Check every
   `kind: "input-table"` element in the harvested spec for row count before
   telling the user data is ready.

## Fix 1 — replace warehouse-backed tables

1. Generate synthetic data with realistic FKs and a fixed "today" anchor
   (`TODAY = date(...)`) so risk trends/date-diffs line up. Reuse one
   generator module across all tables (store list, employee names, FK
   pools) so `RESTAURANT_ID`/`EMPLOYEE_ID` joins stay consistent.
2. Seed each one as a **new** CSV-backed input table via the browser
   recipe below (this is the only way to get real rows into Snowflake
   through the UI without a warehouse-side ETL job).
3. Rewire every downstream element that formerly read the old table:
   rename the new element (`e["name"] = "..._NEW"`), then repoint
   `columns[].formula` on each consumer to the new element's raw
   SCREAMING_SNAKE column ids (new CSV columns have no friendly `name`,
   only the literal CSV header text as `id`) or through a native `join`
   source (`{"kind": "join", "primarySource": ..., "joins": [...]}`) when
   a consumer needs a lookup across two of the new tables. PUT via
   `/v2/workbooks/{id}/spec` as usual.
4. **`Date()` takes exactly one string argument** — `Date("2026-09-21")`,
   not `Date(2026, 9, 21)`. The multi-arg form doesn't fail at PUT time;
   it compiles into a literal error string (`'Date expected 1 argument,
   got 3'`) embedded in the SQL, which then poisons every downstream
   formula that references the errored column. It will NOT show up via
   `scripts/validate-spec.py` or `verify-workbook.sh` (they grep for
   "Unknown column" / "Circular reference" only) — the only way to catch
   it is pulling compiled SQL directly: `GET
   /v2/workbooks/{id}/elements/{elementId}/query` and reading the `sql`
   field for embedded `'...'` error strings.
5. **A bare non-aggregate column referenced inside an aggregate formula
   can silently return `null`.** Sigma's grouped-table compilation dedupes
   bare passthrough columns per group via `iff(equal_null(min(x), max(x)),
   max(x), null)` — if the group's rows disagree on that value (they will,
   for a per-week risk score inside a per-restaurant grouping), the
   deduped value is `null`. If a *different* aggregate formula in the same
   table references that bare column by display name instead of the raw
   qualified source column (e.g. `Max([Weekly Risk Score])` instead of
   `Max([Risk Join/RISK_SCORE])`), it computes over the already-poisoned
   `null`, not the real per-row data — producing a `null` KPI and, for a
   sparkline, an "Error parsing sparkline value" render error. Fix: always
   reference the raw qualified join/source column inside an aggregate that
   sits next to a bare per-row passthrough of the same field, never the
   sibling display name. Confirm the fix by re-pulling compiled SQL and
   checking the aggregate's source expression, not just that the PUT
   succeeded.
   - Watch for **the same conceptual column having different formulas /
     display names across sibling table elements** that both source the
     same join (e.g. one visible table names it "Weekly Risk Score" and
     aggregates with `Max`, a second visible table leaves it unnamed and
     aggregates the same field with `Avg`, auto-naming itself "Avg of
     Risk Score"). Copy-pasting one fix to both siblings verbatim can
     silently change which aggregate function backs a name a third
     element depends on (`[Risk Feed/Avg of Risk Score]`), breaking that
     consumer with `Dependency not found`. Diff each sibling's *original*
     formula before patching, don't assume identical elementIds have
     identical semantics.
6. **A dropped `"image": {"type": "original"}` column config** turns a
   badge-svg-URL formula into visible raw text instead of a rendered
   image. If a status/tier badge column shows a literal `https://...` URL
   after rebrand, diff that column against the original exemplar's same
   column — `image` configs don't always survive a harvest/rebrand pass
   and must be copied back explicitly.

## Fix 2 — seed empty input tables

### Recipe: CSV upload via browser automation (the reliable path)

REST can create structure but not rows. Browser automation through the
real Sigma UI is the only path that produces real rows, because the CSV
upload flow materializes a genuine Snowflake table server-side.

1. Generate one CSV per empty input table, matching its exact column
   **display names** — check the harvested spec for `values: [...]` on any
   column (a picklist/single-select constraint). Sigma renders these as
   colored pill dropdowns; pasting a value outside the allowed list is
   silently rejected for that column while the rest of the row still
   saves. Read every picklist's allowed values from the spec (or from the
   dropdown UI) before generating data — don't guess plausible-sounding
   values like "OK"/"Active"; they will not match.
2. Log in with Playwright (real interactive auth, not API credentials —
   input-table writes require a UI session). Handle MFA if enabled: the
   verification code arrives by email and must be read via whatever
   mail-search tool is available, then fed back into the same browser
   session/process (a single script run — the "trigger email" and "read
   email" steps can't span two separate tool calls if the browser only
   lives in one of them).
3. Navigate to the hidden data page, enter Edit mode. If a "Your document
   is out of date" dialog appears, click "Update to latest version" — this
   is expected when a REST PUT changed the spec since the browser session
   started, and syncing it is safe (it does not discard already-committed
   input-table rows, which live in the backing Snowflake table
   independent of the workbook's draft/published spec state).
4. **Locate the target table reliably — don't blind-scroll by a fixed
   pixel count.** Long hidden data pages virtualize far-off content out of
   the DOM, so `get_by_text(title).scroll_into_view_if_needed()` will
   time out if the title isn't rendered yet. The robust pattern:
   ```python
   page.mouse.move(60, 500)          # left margin — NOT over any grid,
                                       # or you'll scroll that grid's own
                                       # internal row list instead of the
                                       # page (tables with many rows have
                                       # their own scroll capture)
   for i in range(max_steps):
       if title in page.evaluate("document.body.innerText"):
           break
       page.mouse.wheel(0, 1200)
       page.wait_for_timeout(500)
   loc = page.get_by_text(title, exact=True).first
   loc.scroll_into_view_if_needed(timeout=8000)
   page.wait_for_timeout(4000)          # let it fully hydrate — a click
                                          # during the skeleton-loading
                                          # placeholder state lands on
                                          # nothing and silently no-ops
   box = loc.bounding_box()
   ```
   Two title-collision traps to know about: (a) a table title string can
   also appear in an unrelated "Completion Form Controls for Input Table"
   -style section higher up the same page — if `body.innerText` matches
   too early, you're scrolling to the wrong place, not the grid; verify
   with a screenshot before clicking. (b) a picklist-type column with a
   generic name can produce a false match against a DIFFERENT table's
   same-named column further down — when in doubt, screenshot after
   locating and visually confirm the grid's own title/column set before
   pasting.
5. Click into the target table's first data cell — roughly
   `(box.x + 60, box.y + 83)` relative to the title's own bounding box
   (title height + header row + into the first data row). Confirm focus
   with a screenshot (a real blue-bordered editable cell, not a bare
   skeleton row) before proceeding — a click during the loading skeleton
   silently fails and everything downstream (paste, typed values) is lost
   with no error.
6. Build one big TSV block (`\t` between columns, `\n` between rows) from
   the CSV, write it to the OS clipboard via
   `page.evaluate("(t) => navigator.clipboard.writeText(t)", tsv)` (grant
   `clipboard-read`/`clipboard-write` permissions on the context first),
   then `page.keyboard.press("Control+V")`. Paste multiple full rows at
   once — this works and is dramatically faster than cell-by-cell typing.
   Wait 8–10s after paste before screenshotting (real Snowflake writes,
   not instant); check the `SUMMARY` footer's row count (`N rows – M
   columns`), which is scroll-position-independent, rather than trusting
   a screenshot of whichever rows happen to be in the current viewport —
   the grid auto-scrolls after paste to keep the last-written cell
   visible, and it's easy to mistake "rows 8–14 visible, rendered blank
   because row 1 is what's populated and just scrolled off" for "the
   paste failed."
7. Publish (`Publish` button, top toolbar) once satisfied. Row *data*
   writes to Snowflake immediately regardless of draft/published spec
   state — Publish is about the workbook *structure* draft, not the rows —
   but publish anyway so REST GET/PUT and any other session see a
   consistent state.

### Hard rule: never `Ctrl+A` inside an input-table grid to clear rows

Ctrl+A while a cell is focused selects the **entire grid including the
column headers**, and Backspace/Delete on that selection deletes the
**column structure itself**, not just cell contents — every custom column
on that input-table element is gone, with the "Corrective Action
Verified?"/"Photo / File Evidence"-style typed columns collapsing to just
the two immutable system columns (`Created at`, `ID`). This happened once
in production work on this pattern and is expensive to recover from:

- The columns *can* be rebuilt one at a time via the right panel's
  **`+ ADD COLUMN`** button → pick a type → the new column lands at a
  fixed position immediately left of the `+` (re-locate `+` after every
  add if the grid has scrolled horizontally to keep a Date/File column's
  wider cell in view) → double-click the new header to enter its rename
  field → `Ctrl+A`, type the real name, `Enter`. This reliably restores
  the schema (verified by the right panel's column type icons matching
  the original) and Sigma's own change log (Draft menu → Versions →
  Version history) will show a paired `Create input table edits` /
  `Commit input table edits` event per column, confirming each add
  actually committed server-side.
- **But manually-rebuilt columns were not reliably writable in-place** —
  neither a full-row paste nor a single manually-typed cell value
  persisted, across many retries, with generous wait times, and even
  after a full `Publish`. Reads (compiled SQL via
  `GET .../elements/{id}/query`) looked completely normal — correct
  backing column ids, no error markers — so this is not a validation
  rejection you'll see surfaced anywhere; the write just silently doesn't
  take. Root cause undetermined as of this writing.
- **The reliable recovery is to treat it as data loss, not a repair job:**
  CSV-upload a brand-new table with the same columns (the "Fix 1" recipe
  above) and repoint the damaged element's own `source` at it, rather
  than trying to keep writing into the damaged element directly:
  ```json
  {"kind": "linked", "from": "<new-csv-table-elementId>"}
  ```
  This keeps the damaged element's own id (so every existing control/chart
  that references it by elementId+columnId keeps working unchanged) while
  the new CSV table supplies real rows. Two things to get right, both
  discovered the hard way:
  - An `input-table`-kind element's `source` **cannot** be
    `{"kind": "table", "elementId": ...}` (plain passthrough) — PUT
    rejects it with `Invalid kind: "input-table"`. It must be `"linked"`.
  - **Formulas on a `linked` table's columns must reference the linked
    source's raw column ids directly** (`[ACTION_ID]`, matching the new
    CSV table's own column id) — NOT the bare display name pattern used
    elsewhere in this doc for join sources. A bare `[PRIORITY]`-style ref
    inside a linked table's own column formula compiles to a literal
    `'Unknown column "[PRIORITY]"'` string, same failure mode as the
    `Date()` gotcha above.
  - **Check every `insert-rows` action effect targeting the element
    first.** Any button/workflow action with an `insert-rows` effect
    against that `tableElementId` will reject the whole spec at PUT time
    (`cannot insert rows into a linked input table (use update-rows
    instead)`) once you convert it to `linked`. If the effect's `values`
    map is empty (a dead/no-op insert left over from harvest), it's safe
    to delete that one effect from the action's `effects` array; if it
    has real values, the action needs a redesign (`update-rows` against
    an existing row, or a different target) before you can convert the
    table.
  - When reverting a botched attempt back to `{"kind": "empty", ...}`,
    restore each column's original `type` field alongside removing
    `formula` — a column can't have both `type` and `formula` set
    simultaneously, and stripping only `formula` while forgetting to
    restore `type` produces the exact same opaque `Invalid kind:
    "input-table"` PUT error as the original mistake, misleadingly
    pointing at the element's top-level `kind` rather than the real
    column-level cause.

## Generalizing beyond this exemplar

This whole doc is customer-agnostic by construction — none of the recipe
steps depend on Carl's Jr, Chipotle, or any specific column set. When
seeding a new customer:

- Reuse the synthetic-data generator pattern (one Python module, a fixed
  `TODAY` anchor, a shared store/employee list threaded through every
  table for consistent FKs) rather than writing one-off generators per
  table.
- Reuse the Playwright helpers (`pw_session.py`-style context launcher
  with saved storage state, the scroll-until-found + stabilize pattern,
  the clipboard-paste function) as a small library, not copy-pasted
  per-script boilerplate — the failure modes above (skeleton-loading
  clicks, title collisions, auto-scroll-after-paste) recur regardless of
  which table you're seeding.
- Budget real time for this phase. Seeding N empty input tables plus
  rewiring M warehouse-backed tables is not a quick follow-up to a
  branding pass — treat it as its own plan step with its own
  Recon → Plan → User approval cycle, especially since it involves real
  interactive credentials and can hit exactly the kind of destructive
  UI accident documented above.
