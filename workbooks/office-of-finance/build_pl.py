import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".claude/skills/sigma-office-of-finance/scripts"))
import style

CONN_SNOWFLAKE = "a9d45cfe-ff65-4515-8193-a7072602a1ee"
FOLDER_ID = "6dfa8584-aa74-4de6-99cb-ecbbbba668ac"

BASE_COLS = ["Period Month", "Line Order", "Section", "Line Item", "Amount"]


def cols(names, prefix):
    return [{"id": f"{prefix}{i}", "formula": f'[Custom SQL/{n}]', "name": n}
            for i, n in enumerate(names)]


def build_page():
    """Returns (elements, page, layout) for the P&L Statement page."""
    sql_text = (ROOT / ".claude/skills/sigma-office-of-finance/sql/pl_statement.sql").read_text()

    elements = []
    def add(el):
        elements.append(el)
        return el["id"]

    # ---- Table: filtered scope (KPIs, statement pivot) ----
    tbl_id = add({
        "id": "tbl-pl",
        "kind": "table",
        "name": "P&L Statement (Custom SQL)",
        "source": {"connectionId": CONN_SNOWFLAKE, "kind": "sql", "statement": sql_text},
        "columns": cols(BASE_COLS, "pl-col-"),
    })
    COL_PERIOD = "pl-col-0"

    # ---- Table: unfiltered duplicate, trend chart only (needs full 12mo) ----
    tbl_trend_id = add({
        "id": "tbl-pl-trend",
        "kind": "table",
        "name": "P&L Statement — Trend (Custom SQL)",
        "source": {"connectionId": CONN_SNOWFLAKE, "kind": "sql", "statement": sql_text},
        "columns": cols(BASE_COLS, "pl-trend-col-"),
    })

    # ---- Header: title + fiscal-period control ----
    hdr_id = add({"id": "pl-container-header", "kind": "container", "style": style.header_style()})
    title_id = add({
        "id": "pl-text-title",
        "kind": "text",
        "body": style.title_body("P&L Statement — FY26", "(swap fiscal period label per prospect)"),
        "verticalAlign": "middle",
    })
    ctrl_period_id = add({
        "kind": "control",
        "id": "pl-ctrl-period",
        "controlId": "PL-Period",
        "controlType": "list",
        "name": "Period",
        "mode": "include",
        "selectionMode": "single",
        "values": [],
        "source": {"kind": "source", "source": {"kind": "table", "elementId": tbl_id}, "columnId": COL_PERIOD},
        "filters": [{"source": {"kind": "table", "elementId": tbl_id}, "columnId": COL_PERIOD}],
        "style": {"backgroundColor": style.WHITE, "borderRadius": "pill"},
    })

    # ---- KPI row ----
    kpi_row_id = add({"id": "pl-container-kpi-row", "kind": "container"})

    def kpi(id_, name, formula, value_format=style.CURRENCY_FMT, accent=False):
        # No `comparison`/`comparisonColumn` here — none of these four KPIs
        # has a clean same-scale baseline sibling to compare against, and a
        # bare period-column-only `comparison` is rejected live ("requires
        # a comparison column or period comparison") despite what
        # sigma-input-table-app's SKILL.md implies — confirmed 2026-08-24.
        # See build_page1.py's kpi() for the working comparisonColumn form.
        return add({
            "id": id_,
            "kind": "kpi-chart",
            "name": style.kpi_name(name),
            "source": {"kind": "table", "elementId": tbl_id},
            "columns": [
                {"id": f"{id_}-value", "name": name, "formula": formula, "format": value_format},
            ],
            "value": {"columnId": f"{id_}-value", "fontSize": 32},
            "style": style.card_style(accent=accent),
        })

    # Filter by the numeric Line Order (1=Revenue, 3=Gross Profit,
    # 8=Operating Income, 10=Net Income — see sql/pl_statement.sql) rather
    # than a quoted Line Item string match — more robust to a line-item
    # label rename, and avoids a live 403 (Cloudflare-level, not the Sigma
    # API itself) that repeated `[Col] = "text"` comparisons next to the
    # embedded SQL's own SELECT/UNION text triggered — confirmed 2026-08-24.
    revenue_expr = 'SumIf([Custom SQL/Amount], [Custom SQL/Line Order] = 1)'
    gross_profit_expr = 'SumIf([Custom SQL/Amount], [Custom SQL/Line Order] = 3)'
    op_income_expr = 'SumIf([Custom SQL/Amount], [Custom SQL/Line Order] = 8)'
    net_income_expr = 'SumIf([Custom SQL/Amount], [Custom SQL/Line Order] = 10)'

    kpi_revenue_id = kpi("pl-kpi-revenue", "Revenue", revenue_expr, accent=True)
    kpi_gm_id = kpi("pl-kpi-gross-margin", "Gross Margin %",
                     f'({gross_profit_expr}) / ({revenue_expr})', value_format=style.PERCENT_FMT)
    kpi_om_id = kpi("pl-kpi-operating-margin", "Operating Margin %",
                     f'({op_income_expr}) / ({revenue_expr})', value_format=style.PERCENT_FMT)
    kpi_ni_id = kpi("pl-kpi-net-income", "Net Income", net_income_expr)

    # ---- P&L statement pivot — rows sorted by the explicit Line Order
    # column (plain tables have no row-sort field; pivots do, via
    # rowsBy[].sort — reference/specification/tables.md "Shape").
    pivot_id = add({
        "id": "pivot-pl-statement",
        "kind": "pivot-table",
        "name": "P&L Statement",
        "source": {"kind": "table", "elementId": tbl_id},
        "columns": [
            {"id": "piv-line-item", "name": "Line Item", "formula": "[Custom SQL/Line Item]"},
            {"id": "piv-line-order", "name": "Line Order", "formula": "[Custom SQL/Line Order]"},
            {"id": "piv-amount", "name": "Amount", "formula": "Sum([Custom SQL/Amount])",
             "format": style.CURRENCY_FULL_FMT},
        ],
        "rowsBy": [{"id": "piv-line-item", "sort": {"by": "piv-line-order", "direction": "ascending"}}],
        "columnsBy": [],
        "values": ["piv-amount"],
    })

    # ---- Net Income trend, trailing 12 months (unfiltered table) ----
    trend_chart_id = add({
        "id": "bar-pl-net-income-trend",
        "kind": "bar-chart",
        "name": "Net Income — Trailing 12 Months",
        "source": {"kind": "table", "elementId": tbl_trend_id},
        "columns": [
            {"id": "tr-month", "name": "Month", "formula": "[Custom SQL/Period Month]", "format": style.MONTH_FMT},
            {"id": "tr-net-income", "name": "Net Income",
             "formula": 'SumIf([Custom SQL/Amount], [Custom SQL/Line Order] = 10)',
             "format": style.CURRENCY_FMT},
            {"id": "tr-revenue", "name": "Revenue",
             "formula": 'SumIf([Custom SQL/Amount], [Custom SQL/Line Order] = 1)',
             "format": style.CURRENCY_FMT},
        ],
        "xAxis": {"columnId": "tr-month"},
        "yAxis": {"columnIds": ["tr-revenue", "tr-net-income"]},
    })

    page = {"id": "page-pl-statement", "name": "P&L Statement", "pageWidth": style.PAGE_WIDTH}

    layout = f'''<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="page-pl-statement">
  <Container elementId="{hdr_id}" type="grid" gridColumn="1 / 25" gridRow="1 / 4" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <Element elementId="{title_id}" gridColumn="1 / 17" gridRow="1 / 4"/>
    <Element elementId="{ctrl_period_id}" gridColumn="17 / 25" gridRow="1 / 4"/>
  </Container>
  <Container elementId="{kpi_row_id}" type="grid" gridColumn="1 / 25" gridRow="4 / 12" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <Element elementId="{kpi_revenue_id}" gridColumn="1 / 7" gridRow="1 / 9"/>
    <Element elementId="{kpi_gm_id}" gridColumn="7 / 13" gridRow="1 / 9"/>
    <Element elementId="{kpi_om_id}" gridColumn="13 / 19" gridRow="1 / 9"/>
    <Element elementId="{kpi_ni_id}" gridColumn="19 / 25" gridRow="1 / 9"/>
  </Container>
  <Element elementId="{pivot_id}" gridColumn="1 / 13" gridRow="12 / 40"/>
  <Element elementId="{trend_chart_id}" gridColumn="13 / 25" gridRow="12 / 40"/>
  <Element elementId="{tbl_id}" gridColumn="1 / 25" gridRow="40 / 54"/>
  <Element elementId="{tbl_trend_id}" gridColumn="1 / 25" gridRow="54 / 68"/>
</Page>'''

    return elements, page, layout


if __name__ == "__main__":
    import json, datetime
    elements, page, layout = build_page()
    spec = {
        "name": "Office of Finance — P&L Statement (DRAFT)",
        "folderId": FOLDER_ID,
        "document": {
            "schemaVersion": 1, "kind": "workbook", "elements": elements,
            "pages": [page], "layout": f'<?xml version="1.0" encoding="utf-8"?>\n{layout}',
        },
    }
    out = ROOT / "workbooks" / "office-of-finance" / "iterations"
    out.mkdir(parents=True, exist_ok=True)
    outfile = out / f"{datetime.datetime.now().strftime('%Y%m%d-%H%M')}-page-pl-statement.json"
    outfile.write_text(json.dumps(spec, indent=2))
    print("wrote", outfile)
