import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".claude/skills/sigma-office-of-finance/scripts"))
import style

CONN_SNOWFLAKE = "a9d45cfe-ff65-4515-8193-a7072602a1ee"
FOLDER_ID = "6dfa8584-aa74-4de6-99cb-ecbbbba668ac"

# Scope note (see plan): this builds sigma-input-table-app's verified linked-
# input-table foundation — base table -> linked input table with a hidden
# Base Case + editable Forecast Entry + Coalesce + Δ column -> a derived
# "Book" read table (every chart/KPI sources from this, not the input table
# directly) -> comparative KPIs -> baseline-vs-forecast chart. It deliberately
# does NOT build the fuller scenario-create/submit/approve modal workflow
# that skill's SKILL.md also documents — real scope increase beyond "a
# forecasting module," a stated follow-up, not built here.
#
# Shape corrections made 2026-08-24 against the skill's own verified example
# (examples/build_demand_planning_lite.py), which disagrees with SKILL.md's
# prose in two places:
#   1. The linked input table links directly from a plain per-row `table`
#      (no pivot/cross-join needed for a single-scenario grid — pivots are
#      only for the multi-scenario cross-join case this page doesn't need).
#   2. KPIs/charts do NOT source from the linked input table directly
#      (SKILL.md's DEFAULT #3) — the working example inserts a derived
#      "Book" table sourced FROM the input table and points every
#      downstream chart/KPI at that instead. Sourcing a kpi-chart directly
#      from an input-table element produced a masked `Invalid kind:
#      "input-table"` on the *input table itself* at PUT time.


def build_page():
    """Returns (elements, page, layout) for the Rolling Forecast page."""
    sql_text = (ROOT / ".claude/skills/sigma-office-of-finance/sql/rolling_forecast.sql").read_text()

    elements = []
    def add(el):
        elements.append(el)
        return el["id"]

    # ---- Base table: trailing-run-rate baseline by department x future month ----
    base_id = add({
        "id": "tbl-forecast-base",
        "kind": "table",
        "name": "Forecast Baseline (Custom SQL)",
        "source": {"connectionId": CONN_SNOWFLAKE, "kind": "sql", "statement": sql_text},
        "columns": [
            {"id": "base-month", "name": "Period Month", "formula": "[Custom SQL/Period Month]"},
            {"id": "base-dept", "name": "Department", "formula": "[Custom SQL/Department]"},
            {"id": "base-case", "name": "Base Case", "formula": "[Custom SQL/Base Case]"},
        ],
    })

    # ---- Linked input table — the modeling grid, linked directly from the
    # base table (one row per month x department already; no pivot needed
    # for a single implicit scenario — see scope note above). Key-bound
    # columns inherit their display name from the column they key to; no
    # need to redeclare `name` on them. Editable Forecast Entry starts
    # blank; Effective Forecast = Coalesce(entry, Base Case) so the page
    # shows a real (if flat) scenario immediately, not a dead-empty grid.
    forecast_id = add({
        "id": "input-forecast",
        "kind": "input-table",
        "name": "Rolling Forecast — FY26",
        "source": {"kind": "linked", "from": base_id},
        # "view" = editable in the published workbook at all access levels;
        # "edit" = editable in DRAFT only (schema-2026-08-breaking-changes.md
        # -> "Input-table data-entry permission") — we PUT straight to the
        # live/published workbook, so "view" is the correct mode here.
        "inputMode": "view",
        "columns": [
            {"id": "fc-month", "key": "base-month"},
            {"id": "fc-dept", "key": "base-dept"},
            {"id": "fc-base", "key": "base-case"},
            {"id": "fc-entry", "type": "number", "name": "Forecast Entry"},
            {"id": "fc-effective", "name": "Effective Forecast",
             "formula": "Coalesce([Forecast Entry], [Base Case])"},
            {"id": "fc-delta", "name": "Δ vs. Base Case",
             "formula": "Coalesce([Forecast Entry], [Base Case]) - [Base Case]"},
        ],
        "sort": [{"columnId": "fc-month", "direction": "ascending"}],
    })

    # ---- Book — the single downstream read surface every chart/KPI uses
    # (mirrors the verified example; sourcing charts/KPIs straight off the
    # input table is what triggered the Invalid-kind failure above).
    book_id = add({
        "id": "tbl-forecast-book",
        "kind": "table",
        "name": "Forecast Book",
        "source": {"kind": "table", "elementId": forecast_id},
        "columns": [
            {"id": "bk-month", "formula": "[Rolling Forecast — FY26/Period Month]", "name": "Month",
             "format": style.MONTH_FMT},
            {"id": "bk-dept", "formula": "[Rolling Forecast — FY26/Department]", "name": "Department"},
            {"id": "bk-base", "formula": "[Rolling Forecast — FY26/Base Case]", "name": "Base Case",
             "format": style.CURRENCY_FMT},
            {"id": "bk-effective", "formula": "[Rolling Forecast — FY26/Effective Forecast]",
             "name": "Effective Forecast", "format": style.CURRENCY_FMT},
            {"id": "bk-delta", "formula": "[Rolling Forecast — FY26/Δ vs. Base Case]",
             "name": "Δ vs. Base Case", "format": style.CURRENCY_FMT},
        ],
    })

    # ---- Header ----
    hdr_id = add({"id": "fc-container-header", "kind": "container", "style": style.header_style()})
    title_id = add({
        "id": "fc-text-title",
        "kind": "text",
        "body": style.title_body("Rolling Forecast — FY26",
                                  "Type into Forecast Entry to override the seeded Base Case per row"),
        "verticalAlign": "middle",
    })

    # ---- Comparative KPIs, sourced from the Book (see scope note) ----
    kpi_row_id = add({"id": "fc-container-kpi-row", "kind": "container"})

    def comparison_kpi(id_, name, value_formula, baseline_formula, value_format=style.CURRENCY_FMT,
                        good_is_high=True, accent=False):
        return add({
            "id": id_,
            "kind": "kpi-chart",
            "name": style.kpi_name(name),
            "source": {"kind": "table", "elementId": book_id},
            "columns": [
                {"id": f"{id_}-value", "name": name, "formula": value_formula, "format": value_format},
                {"id": f"{id_}-baseline", "name": "Baseline", "formula": baseline_formula,
                 "format": value_format},
            ],
            "value": {"columnId": f"{id_}-value", "fontSize": 32},
            # Comparison-delta vs. a baseline sibling column — verified shape,
            # no date column needed (sigma-input-table-app SKILL.md ->
            # "Verified shape gotchas").
            "comparison": style.kpi_comparison(good_is_high=good_is_high),
            "comparisonColumn": {"columnId": f"{id_}-baseline"},
            "style": style.card_style(accent=accent),
        })

    kpi_projected_id = comparison_kpi(
        "fc-kpi-projected", "Projected Forecast",
        "Sum([Forecast Book/Effective Forecast])", "Sum([Forecast Book/Base Case])", accent=True)
    kpi_uplift_id = add({
        "id": "fc-kpi-uplift", "kind": "kpi-chart", "name": style.kpi_name("Uplift %"),
        "source": {"kind": "table", "elementId": book_id},
        "columns": [{"id": "fc-kpi-uplift-value", "name": "Uplift %",
                     "formula": "(Sum([Forecast Book/Effective Forecast]) - Sum([Forecast Book/Base Case])) / Sum([Forecast Book/Base Case])",
                     "format": style.PERCENT_FMT}],
        "value": {"columnId": "fc-kpi-uplift-value", "fontSize": 32},
        "style": style.card_style(),
    })
    kpi_baseline_id = add({
        "id": "fc-kpi-baseline", "kind": "kpi-chart", "name": style.kpi_name("Baseline (Run-Rate)"),
        "source": {"kind": "table", "elementId": book_id},
        "columns": [{"id": "fc-kpi-baseline-value", "name": "Baseline",
                     "formula": "Sum([Forecast Book/Base Case])", "format": style.CURRENCY_FMT}],
        "value": {"columnId": "fc-kpi-baseline-value", "fontSize": 32},
        "style": style.card_style(),
    })

    # ---- Baseline vs. Forecast by department — grouped, stacking:"none"
    # (the #1 gotcha: two y-series stack by default and silently render
    # their SUM, looking plausible while being wrong).
    compare_chart_id = add({
        "id": "bar-forecast-vs-baseline",
        "kind": "bar-chart",
        "name": "Baseline vs. Forecast by Department",
        "source": {"kind": "table", "elementId": book_id},
        "columns": [
            {"id": "cmp-dept", "name": "Department", "formula": "[Forecast Book/Department]"},
            {"id": "cmp-base", "name": "Base Case", "formula": "Sum([Forecast Book/Base Case])",
             "format": style.CURRENCY_FMT},
            {"id": "cmp-forecast", "name": "Effective Forecast", "formula": "Sum([Forecast Book/Effective Forecast])",
             "format": style.CURRENCY_FMT},
        ],
        "xAxis": {"columnId": "cmp-dept"},
        "yAxis": {"columnIds": ["cmp-base", "cmp-forecast"]},
        "stacking": "none",
    })

    # ---- Variance chart: Effective Forecast - Base Case, by department ----
    variance_chart_id = add({
        "id": "bar-forecast-variance",
        "kind": "bar-chart",
        "name": "Forecast Variance vs. Baseline",
        "source": {"kind": "table", "elementId": book_id},
        "columns": [
            {"id": "var-month", "name": "Month", "formula": "[Forecast Book/Month]", "format": style.MONTH_FMT},
            {"id": "var-dept", "name": "Department", "formula": "[Forecast Book/Department]"},
            {"id": "var-base", "name": "Base Case", "formula": "Sum([Forecast Book/Base Case])",
             "format": style.CURRENCY_FMT},
            {"id": "var-effective", "name": "Effective Forecast",
             "formula": "Sum([Forecast Book/Effective Forecast])", "format": style.CURRENCY_FMT},
            {"id": "var-delta", "name": "Δ vs. Base Case", "formula": "Sum([Forecast Book/Δ vs. Base Case])",
             "format": style.CURRENCY_FMT},
        ],
        "xAxis": {"columnId": "var-dept"},
        "yAxis": {"columnIds": ["var-delta"]},
    })

    page = {"id": "page-rolling-forecast", "name": "Rolling Forecast", "pageWidth": style.PAGE_WIDTH}

    layout = f'''<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="page-rolling-forecast">
  <Container elementId="{hdr_id}" type="grid" gridColumn="1 / 25" gridRow="1 / 4" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <Element elementId="{title_id}" gridColumn="1 / 25" gridRow="1 / 4"/>
  </Container>
  <Container elementId="{kpi_row_id}" type="grid" gridColumn="1 / 25" gridRow="4 / 12" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <Element elementId="{kpi_projected_id}" gridColumn="1 / 9" gridRow="1 / 9"/>
    <Element elementId="{kpi_uplift_id}" gridColumn="9 / 17" gridRow="1 / 9"/>
    <Element elementId="{kpi_baseline_id}" gridColumn="17 / 25" gridRow="1 / 9"/>
  </Container>
  <Element elementId="{forecast_id}" gridColumn="1 / 25" gridRow="12 / 34"/>
  <Element elementId="{compare_chart_id}" gridColumn="1 / 13" gridRow="34 / 54"/>
  <Element elementId="{variance_chart_id}" gridColumn="13 / 25" gridRow="34 / 54"/>
  <Element elementId="{base_id}" gridColumn="1 / 25" gridRow="54 / 68"/>
  <Element elementId="{book_id}" gridColumn="1 / 25" gridRow="68 / 82"/>
</Page>'''

    return elements, page, layout


if __name__ == "__main__":
    import json, datetime
    elements, page, layout = build_page()
    spec = {
        "name": "Office of Finance — Rolling Forecast (DRAFT)",
        "folderId": FOLDER_ID,
        "document": {
            "schemaVersion": 1, "kind": "workbook", "elements": elements,
            "pages": [page], "layout": f'<?xml version="1.0" encoding="utf-8"?>\n{layout}',
        },
    }
    out = ROOT / "workbooks" / "office-of-finance" / "iterations"
    out.mkdir(parents=True, exist_ok=True)
    outfile = out / f"{datetime.datetime.now().strftime('%Y%m%d-%H%M')}-page-rolling-forecast.json"
    outfile.write_text(json.dumps(spec, indent=2))
    print("wrote", outfile)
