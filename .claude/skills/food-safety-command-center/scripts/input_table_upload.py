"""
input_table_upload.py — reusable browser-automation CSV-upload helper.

Implements the recipe documented in reference/data-seeding.md: locate an
input table on a hidden/visible data page by its visible title, click
into its first data cell, paste a clipboard TSV blob built from a CSV
file, verify the row count via the table's own SUMMARY footer, then
Publish.

Requires a Playwright `page` already logged in (see sigma_session.py)
and already navigated to the target workbook's edit URL
(".../edit"). Does not handle login or navigation to the workbook --
callers own that, since it varies per workflow (new workbook vs.
existing one, "document out of date" dialog handling, etc).

**Never issues Ctrl+A inside a table grid.** Selecting the whole grid
(including headers) and deleting collapses the table's columns down to
just its system columns -- a real, destructive incident this pattern
caused once already (see history.md's Ctrl+A entry). This module only
ever clicks a single cell before pasting.
"""
import csv
import time


def switch_to_page(page, page_name):
    """Click a page tab in the bottom tab bar by its exact visible name.
    Hidden pages (e.g. "Data Model") still render a tab here in the
    editor -- `visibility: "hidden"` only affects the published viewer's
    tab bar, not the editor's. Text elsewhere on the page (KPI labels,
    AI narrative, etc.) could coincidentally match a page name, so this
    is only safe to call with page names, not table titles -- callers
    must know which is which."""
    page.get_by_text(page_name, exact=True).first.click()
    page.wait_for_timeout(2000)


def scroll_until_visible(page, title, max_steps=40, step_px=1200):
    """Long data pages virtualize far-off content out of the DOM -- blind
    pixel-count scrolling misses a table that hasn't rendered yet. Scroll
    from the left margin (not over any grid, or you'll scroll that grid's
    own internal row list instead of the page) until the title appears."""
    page.mouse.move(60, 500)
    for _ in range(max_steps):
        if title in page.inner_text("body"):
            break
        page.mouse.wheel(0, step_px)
        page.wait_for_timeout(500)
    else:
        raise RuntimeError(f"table titled '{title}' never appeared after {max_steps} scroll steps")

    loc = page.get_by_text(title, exact=True).first
    loc.scroll_into_view_if_needed(timeout=8000)
    page.wait_for_timeout(4000)  # let it fully hydrate before any click
    return loc


def _first_data_cell_box(table_title_locator):
    """The first editable cell sits just below the header row, at the
    left edge of the table card."""
    box = table_title_locator.bounding_box()
    return {"x": box["x"] + 20, "y": box["y"] + 70}


def paste_csv_into_table(page, title, csv_path, delimiter=",", verify_timeout_s=15):
    """Pastes every data row of csv_path into the table titled `title`.
    Returns the row count reported by the table's SUMMARY footer after
    the paste settles."""
    loc = scroll_until_visible(page, title)
    cell = _first_data_cell_box(loc)
    page.mouse.click(cell["x"], cell["y"])
    page.wait_for_timeout(500)

    with open(csv_path, newline="") as f:
        rows = list(csv.reader(f, delimiter=delimiter))
    header, data_rows = rows[0], rows[1:]
    tsv_blob = "\n".join("\t".join(str(v) for v in row) for row in data_rows)

    page.evaluate(
        "(text) => navigator.clipboard.writeText(text)",
        tsv_blob,
    )
    page.keyboard.press("Control+V")
    page.wait_for_timeout(max(8000, verify_timeout_s * 1000 // 2))

    return read_row_count(page, title, timeout_s=verify_timeout_s)


def read_row_count(page, title, timeout_s=15):
    """Reads 'N rows' from the table's own SUMMARY footer -- do not trust
    a viewport screenshot for this; post-paste auto-scroll can put the
    footer out of frame while the paste is still finishing."""
    deadline = time.time() + timeout_s
    last_text = None
    while time.time() < deadline:
        body = page.inner_text("body")
        idx = body.find("SUMMARY")
        if idx != -1:
            snippet = body[idx: idx + 60]
            last_text = snippet
            for token in snippet.split():
                if token.isdigit():
                    return int(token)
        time.sleep(1)
    raise RuntimeError(f"could not read a row count from SUMMARY footer near '{title}'; last seen: {last_text!r}")


def publish(page):
    page.get_by_role("button", name="Publish", exact=True).click()
    page.wait_for_timeout(3000)


def dismiss_out_of_date_dialog_if_present(page, timeout_ms=3000):
    """'Your document is out of date' can appear if a REST PUT changed
    the spec since this browser session started. Safe to accept --
    syncing does not discard already-committed input-table rows, which
    live in the backing table independent of the workbook's draft/
    published spec state.

    `exact=True` deliberately -- a fuzzy substring match risks clicking
    an unrelated control if some other panel (version history, etc.) is
    also on screen with overlapping text. A live test session saw a
    "Successfully restored previous version" toast immediately after
    this call, and the input-tables' pasted rows were gone afterward;
    never fully root-caused (correlation, not proven causation -- the
    exact button clicked wasn't captured), but exact matching removes
    one plausible way for this call to hit the wrong element, and costs
    nothing if the dialog's button text is stable."""
    try:
        btn = page.get_by_text("Update to latest version", exact=True)
        btn.wait_for(timeout=timeout_ms)
        btn.click()
        page.wait_for_timeout(2000)
        return True
    except Exception:
        return False
