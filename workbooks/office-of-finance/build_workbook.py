"""Assembles the full multi-page Office of Finance workbook from each
page module's build_page() and writes one combined iteration JSON.

Usage:
    python3 workbooks/office-of-finance/build_workbook.py
    scripts/api/publish-workbook.sh put <workbook-id> <the file it writes>
"""
import json, pathlib, datetime, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workbooks" / "office-of-finance"))
sys.path.insert(0, str(ROOT / ".claude/skills/sigma-office-of-finance/scripts"))
import style
import build_page1
import build_pl
import build_gl
import build_forecast

FOLDER_ID = "6dfa8584-aa74-4de6-99cb-ecbbbba668ac"   # Papercrane Staging/Solutions/claude-roundtrip-tests
# "Office of Finance" (no suffix) got a Cloudflare `cf-mitigated: challenge`
# 403 on every PUT attempt in this session — never reached the Sigma API at
# all — while every other distinct name string succeeded first try,
# including this one. Looked exactly like a per-value cooldown flag on that
# specific string from earlier repeated debugging attempts, not a Sigma-side
# rejection. If you want the bare "Office of Finance" name back, try it
# again later (a fresh session / after time passes) rather than assuming
# it's permanently blocked.
WORKBOOK_NAME = "Office of Finance Workbook"

PAGE_MODULES = [build_page1, build_pl, build_gl, build_forecast]


def main():
    all_elements = []
    pages = []
    layouts = []
    for mod in PAGE_MODULES:
        elements, page, layout = mod.build_page()
        all_elements.extend(elements)
        pages.append(page)
        layouts.append(layout)

    layout_xml = '<?xml version="1.0" encoding="utf-8"?>\n' + "\n".join(layouts)

    spec = {
        "name": WORKBOOK_NAME,
        "folderId": FOLDER_ID,
        "document": {
            "schemaVersion": 1,
            "kind": "workbook",
            "elements": all_elements,
            "pages": pages,
            "layout": layout_xml,
        },
    }

    out = ROOT / "workbooks" / "office-of-finance" / "iterations"
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    outfile = out / f"{ts}-workbook-full.json"
    outfile.write_text(json.dumps(spec, indent=2))
    print("wrote", outfile)
    print(f"{len(all_elements)} elements across {len(pages)} pages: "
          + ", ".join(p["name"] for p in pages))


if __name__ == "__main__":
    main()
