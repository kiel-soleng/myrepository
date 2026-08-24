import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".claude/skills/sigma-office-of-finance/scripts"))
import style

CONN_SNOWFLAKE = "a9d45cfe-ff65-4515-8193-a7072602a1ee"
FOLDER_ID = "6dfa8584-aa74-4de6-99cb-ecbbbba668ac"

BASE_COLS = ["Entry ID", "Entry Date", "Category", "Account", "Description", "Debit", "Credit"]


def cols(names, prefix):
    return [{"id": f"{prefix}{i}", "formula": f'[Custom SQL/{n}]', "name": n}
            for i, n in enumerate(names)]


def build_page():
    """Returns (elements, page, layout) for the General Ledger page."""
    sql_text = (ROOT / ".claude/skills/sigma-office-of-finance/sql/general_ledger.sql").read_text()

    elements = []
    def add(el):
        elements.append(el)
        return el["id"]

    tbl_id = add({
        "id": "tbl-gl",
        "kind": "table",
        "name": "General Ledger (Custom SQL)",
        "source": {"connectionId": CONN_SNOWFLAKE, "kind": "sql", "statement": sql_text},
        "columns": cols(BASE_COLS, "gl-col-"),
    })
    COL_CATEGORY = "gl-col-2"
    COL_ACCOUNT = "gl-col-3"

    # ---- Header: title + account/category controls ----
    hdr_id = add({"id": "gl-container-header", "kind": "container", "style": style.header_style()})
    title_id = add({
        "id": "gl-text-title",
        "kind": "text",
        "body": style.title_body("General Ledger — FY26", "Trailing ~4 months of journal-entry detail"),
        "verticalAlign": "middle",
    })
    ctrl_category_id = add({
        "kind": "control",
        "id": "gl-ctrl-category",
        "controlId": "GL-Category",
        "controlType": "list",
        "name": "Category",
        "mode": "include",
        "selectionMode": "multiple",
        "values": [],
        "source": {"kind": "source", "source": {"kind": "table", "elementId": tbl_id}, "columnId": COL_CATEGORY},
        "filters": [{"source": {"kind": "table", "elementId": tbl_id}, "columnId": COL_CATEGORY}],
        "style": {"backgroundColor": style.WHITE, "borderRadius": "pill"},
    })
    ctrl_account_id = add({
        "kind": "control",
        "id": "gl-ctrl-account",
        "controlId": "GL-Account",
        "controlType": "list",
        "name": "Account",
        "mode": "include",
        "selectionMode": "multiple",
        "values": [],
        "source": {"kind": "source", "source": {"kind": "table", "elementId": tbl_id}, "columnId": COL_ACCOUNT},
        "filters": [{"source": {"kind": "table", "elementId": tbl_id}, "columnId": COL_ACCOUNT}],
        "style": {"backgroundColor": style.WHITE, "borderRadius": "pill"},
    })

    # ---- KPI row — trial-balance sanity check + activity volume ----
    kpi_row_id = add({"id": "gl-container-kpi-row", "kind": "container"})

    def kpi(id_, name, formula, value_format=style.CURRENCY_FULL_FMT, good_is_high=True, accent=False,
            baseline_name=None, baseline_formula=None):
        # comparisonColumn only — a bare period-column `comparison` is
        # rejected live ("requires a comparison column or period
        # comparison") despite sigma-input-table-app's SKILL.md implying
        # a date column alone suffices; confirmed 2026-08-24. See
        # build_page1.py's kpi() for the same fix.
        columns = [{"id": f"{id_}-value", "name": name, "formula": formula, "format": value_format}]
        extra = {}
        if baseline_formula:
            columns.append({"id": f"{id_}-baseline", "name": baseline_name or "Baseline",
                             "formula": baseline_formula, "format": value_format})
            extra["comparison"] = style.kpi_comparison(good_is_high=good_is_high)
            extra["comparisonColumn"] = {"columnId": f"{id_}-baseline"}
        return add({
            "id": id_,
            "kind": "kpi-chart",
            "name": style.kpi_name(name),
            "source": {"kind": "table", "elementId": tbl_id},
            "columns": columns,
            "value": {"columnId": f"{id_}-value", "fontSize": 32},
            "style": style.card_style(accent=accent),
            **extra,
        })

    # Total Debits vs. Total Credits is the natural trial-balance pairing —
    # the delta arrow directly shows whether the ledger is balanced.
    kpi_debits_id = kpi("gl-kpi-debits", "Total Debits", "Sum([Custom SQL/Debit])", accent=True,
        baseline_name="Credits", baseline_formula="Sum([Custom SQL/Credit])")
    kpi_credits_id = kpi("gl-kpi-credits", "Total Credits", "Sum([Custom SQL/Credit])")
    # Should read ~$0 if the ledger is balanced — a genuine data-quality
    # signal, not just decoration.
    kpi_net_id = kpi("gl-kpi-net", "Net (Dr − Cr)",
                      "Sum([Custom SQL/Debit]) - Sum([Custom SQL/Credit])", good_is_high=False)
    kpi_count_id = kpi("gl-kpi-count", "Entry Lines", "Count([Custom SQL/Entry ID])",
                        value_format=style.INT_FMT)

    # ---- Trial balance: net activity by account ----
    trial_balance_id = add({
        "id": "pivot-gl-trial-balance",
        "kind": "pivot-table",
        "name": "Trial Balance by Account",
        "source": {"kind": "table", "elementId": tbl_id},
        "columns": [
            {"id": "tb-account", "name": "Account", "formula": "[Custom SQL/Account]"},
            {"id": "tb-debit", "name": "Total Debit", "formula": "Sum([Custom SQL/Debit])",
             "format": style.CURRENCY_FULL_FMT},
            {"id": "tb-credit", "name": "Total Credit", "formula": "Sum([Custom SQL/Credit])",
             "format": style.CURRENCY_FULL_FMT},
            {"id": "tb-net", "name": "Net", "formula": "Sum([Custom SQL/Debit]) - Sum([Custom SQL/Credit])",
             "format": style.CURRENCY_FULL_FMT},
        ],
        "rowsBy": [{"id": "tb-account", "sort": {"by": "tb-debit", "direction": "descending"}}],
        "columnsBy": [],
        "values": ["tb-debit", "tb-credit", "tb-net"],
    })

    # ---- GL detail table (filterable by the two controls above) ----
    detail_id = add({
        "id": "table-gl-detail",
        "kind": "table",
        "name": "Journal Entry Detail",
        "source": {"kind": "table", "elementId": tbl_id},
        "columns": [
            {"id": "dt-date", "name": "Entry Date", "formula": "[Custom SQL/Entry Date]", "format": style.DATE_FMT},
            {"id": "dt-id", "name": "Entry ID", "formula": "[Custom SQL/Entry ID]"},
            {"id": "dt-category", "name": "Category", "formula": "[Custom SQL/Category]"},
            {"id": "dt-account", "name": "Account", "formula": "[Custom SQL/Account]"},
            {"id": "dt-description", "name": "Description", "formula": "[Custom SQL/Description]"},
            {"id": "dt-debit", "name": "Debit", "formula": "[Custom SQL/Debit]", "format": style.CURRENCY_FULL_FMT},
            {"id": "dt-credit", "name": "Credit", "formula": "[Custom SQL/Credit]", "format": style.CURRENCY_FULL_FMT},
        ],
    })

    page = {"id": "page-general-ledger", "name": "General Ledger", "pageWidth": style.PAGE_WIDTH}

    layout = f'''<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="page-general-ledger">
  <Container elementId="{hdr_id}" type="grid" gridColumn="1 / 25" gridRow="1 / 4" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <Element elementId="{title_id}" gridColumn="1 / 13" gridRow="1 / 4"/>
    <Element elementId="{ctrl_category_id}" gridColumn="13 / 19" gridRow="1 / 4"/>
    <Element elementId="{ctrl_account_id}" gridColumn="19 / 25" gridRow="1 / 4"/>
  </Container>
  <Container elementId="{kpi_row_id}" type="grid" gridColumn="1 / 25" gridRow="4 / 12" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <Element elementId="{kpi_debits_id}" gridColumn="1 / 7" gridRow="1 / 9"/>
    <Element elementId="{kpi_credits_id}" gridColumn="7 / 13" gridRow="1 / 9"/>
    <Element elementId="{kpi_net_id}" gridColumn="13 / 19" gridRow="1 / 9"/>
    <Element elementId="{kpi_count_id}" gridColumn="19 / 25" gridRow="1 / 9"/>
  </Container>
  <Element elementId="{trial_balance_id}" gridColumn="1 / 25" gridRow="12 / 30"/>
  <Element elementId="{detail_id}" gridColumn="1 / 25" gridRow="30 / 58"/>
  <Element elementId="{tbl_id}" gridColumn="1 / 25" gridRow="58 / 72"/>
</Page>'''

    return elements, page, layout


if __name__ == "__main__":
    import json, datetime
    elements, page, layout = build_page()
    spec = {
        "name": "Office of Finance — General Ledger (DRAFT)",
        "folderId": FOLDER_ID,
        "document": {
            "schemaVersion": 1, "kind": "workbook", "elements": elements,
            "pages": [page], "layout": f'<?xml version="1.0" encoding="utf-8"?>\n{layout}',
        },
    }
    out = ROOT / "workbooks" / "office-of-finance" / "iterations"
    out.mkdir(parents=True, exist_ok=True)
    outfile = out / f"{datetime.datetime.now().strftime('%Y%m%d-%H%M')}-page-general-ledger.json"
    outfile.write_text(json.dumps(spec, indent=2))
    print("wrote", outfile)
