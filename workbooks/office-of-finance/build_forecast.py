import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".claude/skills/sigma-office-of-finance/scripts"))
import style

CONN_SNOWFLAKE = "a9d45cfe-ff65-4515-8193-a7072602a1ee"
FOLDER_ID = "6dfa8584-aa74-4de6-99cb-ecbbbba668ac"

# Scope note (see plan): scenario modeling as an "adjust-and-save workbench,"
# not the cross-join scenario-list -> pivot -> linked-input-table pattern
# sigma-input-table-app's SKILL.md prose describes. Two things ruled that
# pattern out:
#   1. Its own cited evidence (reference/scenario-modeler-pattern.md,
#      sigma-company-dashboard/examples/build_cava.py) does not exist
#      anywhere in this repo — prose pointing at nothing.
#   2. sigma-workbook-conventions/reference/specification/sources.md (line
#      273) states plainly: "Sigma's `join` source is warehouse-only — it
#      operates on warehouse tables, not workbook elements." A cross-join of
#      a live user-input table against the forecast base table cannot be
#      built at the spec layer, verified pattern or not.
#
# Instead: two numeric-parameter controls (verified shape — controls.md ->
# "Numeric parameter control referenced from formulas") drive a live-
# updating projected total via bare [<controlId>] formula refs (no join
# needed). A "Save Scenario" button snapshots the current name + drivers +
# computed outcome as a new row in an append-only log input-table via
# insert-rows, so scenarios are named, comparable, and persisted without any
# element-to-element join.
#
# BASE_CASE_TOTAL below is a baked build-time constant (see comment at its
# definition) for the same reason: a formula on the scenario log (or its
# Book) cannot reference `Sum([Forecast Book/Base Case])` — that's a
# cross-table aggregate reference outside the log's own source lineage,
# which validate.md's column-reference rules confirm is not a valid
# qualified-ref case (only: sibling, Metrics, warehouse path segment, the
# element's own `table`-source parent, or a join leg — Book is none of
# those relative to the log). The live-preview KPI uses the same baked
# constant for consistency with what gets saved.
#
# `insert-rows`'s exact JSON shape has no concrete example anywhere in this
# repo (only `update-rows` does, in the effect-enum doc and in
# sigma-input-table-app's real example script). It's inferred here as
# `{"effect": "insert-rows", "table": <id>, "values": {...}}` by dropping
# `whichRows` from the verified `update-rows` shape (nothing to select for a
# brand-new row). This is a first attempt — the required verification step
# is a live click-test in the UI, not just a clean compile/validate pass.

# Baked 2026-08-25 from a direct CSV export of tbl-forecast-base (6 months x
# 5 departments, flat per month): 6 * (182000+264333+2510333+604667+472000).
# Recompute (export tbl-forecast-base, sum Base Case) if rolling_forecast.sql
# changes.
BASE_CASE_TOTAL = 24199998

GROWTH_CTRL = "ScenarioGrowthPct"
COST_CTRL = "ScenarioCostPct"
NAME_CTRL = "ScenarioName"

PROJECTED_FORMULA = (
    f"{BASE_CASE_TOTAL} * (1 + [{GROWTH_CTRL}]/100) * (1 - [{COST_CTRL}]/100)"
)
DELTA_FORMULA = f"({PROJECTED_FORMULA}) - {BASE_CASE_TOTAL}"


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

    # ---- Book — read surface for the baseline (unchanged from the
    # single-scenario build; still the reference line the workbench compares
    # against, and shown at the bottom of the page for transparency).
    book_id = add({
        "id": "tbl-forecast-book",
        "kind": "table",
        "name": "Forecast Book",
        "source": {"kind": "table", "elementId": base_id},
        "columns": [
            {"id": "bk-month", "formula": "[Forecast Baseline (Custom SQL)/Period Month]", "name": "Month",
             "format": style.MONTH_FMT},
            {"id": "bk-dept", "formula": "[Forecast Baseline (Custom SQL)/Department]", "name": "Department"},
            {"id": "bk-base", "formula": "[Forecast Baseline (Custom SQL)/Base Case]", "name": "Base Case",
             "format": style.CURRENCY_FMT},
        ],
    })

    # ---- Header ----
    hdr_id = add({"id": "fc-container-header", "kind": "container", "style": style.header_style()})
    title_id = add({
        "id": "fc-text-title",
        "kind": "text",
        "body": style.title_body("Rolling Forecast — FY26",
                                  "Adjust the assumptions below, name a scenario, and save it to compare"),
        "verticalAlign": "middle",
    })

    # ---- Scenario controls row ----
    ctrl_row_id = add({"id": "fc-container-controls", "kind": "container", "style": style.card_style()})

    growth_pcts = [-10, -5, 0, 5, 10, 15, 20, 25, 30]
    ctrl_growth_id = add({
        "id": "ctrl-scenario-growth",
        "kind": "control",
        "controlId": GROWTH_CTRL,
        "name": "Revenue Growth Adj. %",
        "controlType": "segmented",
        "source": {
            "kind": "manual", "valueType": "number",
            "values": growth_pcts,
            "labels": [f"{p:+d}%" if p else "0%" for p in growth_pcts],
        },
        "value": 0,
    })

    cost_pcts = [-10, -5, 0, 5, 10, 15, 20]
    ctrl_cost_id = add({
        "id": "ctrl-scenario-cost",
        "kind": "control",
        "controlId": COST_CTRL,
        "name": "Cost Change Adj. %",
        "controlType": "segmented",
        "source": {
            "kind": "manual", "valueType": "number",
            "values": cost_pcts,
            "labels": [f"{p:+d}%" if p else "0%" for p in cost_pcts],
        },
        "value": 0,
    })

    ctrl_name_id = add({
        "id": "ctrl-scenario-name",
        "kind": "control",
        "controlId": NAME_CTRL,
        "name": "New Scenario Name",
        "controlType": "text",
        "mode": "equals",
        "case": "insensitive",
        "value": "",
    })

    # ---- Scenario log — append-only input-table. insert-rows values are
    # formulas over the two controls + the baked BASE_CASE_TOTAL constant
    # only (no cross-table reference — see module docstring). System columns
    # CREATED_AT/CREATED_BY are auto-populated by Sigma; never passed as
    # insert values (sigma-input-table-app SKILL.md -> "Adjustments +
    # change-log data app").
    log_id = add({
        "id": "input-scenario-log",
        "kind": "input-table",
        "name": "Scenario Log",
        "source": {"kind": "empty", "connectionId": CONN_SNOWFLAKE},
        "inputMode": "view",
        "columns": [
            {"id": "log-name", "type": "text", "name": "Scenario Name"},
            {"id": "log-growth", "type": "number", "name": "Revenue Growth %"},
            {"id": "log-cost", "type": "number", "name": "Cost Change %"},
            {"id": "log-projected", "type": "number", "name": "Projected Total"},
            {"id": "log-delta", "type": "number", "name": "Δ vs. Base Case"},
            {"id": "CREATED_AT"},
            {"id": "CREATED_BY"},
        ],
    })

    btn_save_id = add({
        "id": "btn-save-scenario",
        "kind": "button",
        "text": "Save Scenario",
        "appearance": "filled",
        "align": "stretch",
        "actions": [{
            "id": "act-save-scenario",
            "trigger": "on-click",
            "effects": [
                {
                    "effect": "insert-rows",
                    "table": log_id,
                    "values": {
                        "log-name": {"type": "formula", "formula": f"[{NAME_CTRL}]"},
                        "log-growth": {"type": "formula", "formula": f"[{GROWTH_CTRL}]"},
                        "log-cost": {"type": "formula", "formula": f"[{COST_CTRL}]"},
                        "log-projected": {"type": "formula", "formula": PROJECTED_FORMULA},
                        "log-delta": {"type": "formula", "formula": DELTA_FORMULA},
                    },
                },
                {"effect": "clear-control", "scope": {"type": "control", "control": NAME_CTRL}},
            ],
        }],
    })

    btn_reset_id = add({
        "id": "btn-reset-scenario",
        "kind": "button",
        "text": "Reset assumptions",
        "appearance": "outline",
        "align": "stretch",
        "actions": [{
            "id": "act-reset-scenario",
            "trigger": "on-click",
            "effects": [
                {"effect": "set-control-value", "control": GROWTH_CTRL,
                 "value": {"type": "constant", "value": {"type": "number", "value": 0}}},
                {"effect": "set-control-value", "control": COST_CTRL,
                 "value": {"type": "constant", "value": {"type": "number", "value": 0}}},
                {"effect": "clear-control", "scope": {"type": "control", "control": NAME_CTRL}},
            ],
        }],
    })

    # ---- Live-preview KPI row — updates as the user moves either control,
    # before anything is saved. Sourced from Book for schema validity, but
    # the formulas below don't reference Book's columns at all (see module
    # docstring on BASE_CASE_TOTAL); "Baseline (Run-Rate)" is the one KPI
    # that DOES read Book live, since Sum() of its own source is a safe
    # same-lineage reference.
    kpi_row_id = add({"id": "fc-container-kpi-row", "kind": "container"})

    kpi_preview_id = add({
        "id": "fc-kpi-preview",
        "kind": "kpi-chart",
        "name": style.kpi_name("Scenario Projected (Live)"),
        "source": {"kind": "table", "elementId": book_id},
        "columns": [
            {"id": "fc-kpi-preview-value", "name": "Scenario Projected",
             "formula": PROJECTED_FORMULA, "format": style.CURRENCY_FMT},
            {"id": "fc-kpi-preview-baseline", "name": "Baseline",
             "formula": str(BASE_CASE_TOTAL), "format": style.CURRENCY_FMT},
        ],
        "value": {"columnId": "fc-kpi-preview-value", "fontSize": 32},
        "comparison": style.kpi_comparison(good_is_high=True),
        "comparisonColumn": {"columnId": "fc-kpi-preview-baseline"},
        "style": style.card_style(accent=True),
    })
    kpi_uplift_id = add({
        "id": "fc-kpi-uplift", "kind": "kpi-chart", "name": style.kpi_name("Uplift % (Live)"),
        "source": {"kind": "table", "elementId": book_id},
        "columns": [{"id": "fc-kpi-uplift-value", "name": "Uplift %",
                     "formula": f"(({PROJECTED_FORMULA}) - {BASE_CASE_TOTAL}) / {BASE_CASE_TOTAL}",
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

    # ---- Scenario Log Book — derived read surface for every saved-scenario
    # KPI/table/chart below (Book-indirection rule: never source a chart/KPI
    # straight off an input-table).
    log_book_id = add({
        "id": "tbl-scenario-log-book",
        "kind": "table",
        "name": "Scenario Log Book",
        "source": {"kind": "table", "elementId": log_id},
        "columns": [
            {"id": "slb-name", "formula": "[Scenario Log/Scenario Name]", "name": "Scenario Name"},
            {"id": "slb-growth", "formula": "[Scenario Log/Revenue Growth %]", "name": "Revenue Growth %",
             "format": style.INT_FMT},
            {"id": "slb-cost", "formula": "[Scenario Log/Cost Change %]", "name": "Cost Change %",
             "format": style.INT_FMT},
            {"id": "slb-projected", "formula": "[Scenario Log/Projected Total]", "name": "Projected Total",
             "format": style.CURRENCY_FMT},
            {"id": "slb-delta", "formula": "[Scenario Log/Δ vs. Base Case]", "name": "Δ vs. Base Case",
             "format": style.CURRENCY_FMT},
        ],
    })

    kpi_count_id = add({
        "id": "fc-kpi-scenario-count", "kind": "kpi-chart", "name": style.kpi_name("Scenarios Saved"),
        "source": {"kind": "table", "elementId": log_book_id},
        "columns": [{"id": "fc-kpi-count-value", "name": "Scenarios Saved",
                     "formula": "CountDistinct([Scenario Log Book/Scenario Name])", "format": style.INT_FMT}],
        "value": {"columnId": "fc-kpi-count-value", "fontSize": 32},
        "style": style.card_style(),
    })
    kpi_best_id = add({
        "id": "fc-kpi-scenario-best", "kind": "kpi-chart", "name": style.kpi_name("Best Saved Scenario"),
        "source": {"kind": "table", "elementId": log_book_id},
        "columns": [{"id": "fc-kpi-best-value", "name": "Best Saved Scenario",
                     "formula": "Max([Scenario Log Book/Projected Total])", "format": style.CURRENCY_FMT}],
        "value": {"columnId": "fc-kpi-best-value", "fontSize": 32},
        "style": style.card_style(),
    })

    # ---- Saved-scenario comparison chart — each save already produces its
    # own row (no cross-join / long-format trick needed for a true N-way
    # comparison, unlike the 2-series baseline-vs-forecast case this page
    # used to have).
    compare_chart_id = add({
        "id": "bar-scenario-comparison",
        "kind": "bar-chart",
        "name": "Saved Scenarios — Projected Total",
        "source": {"kind": "table", "elementId": log_book_id},
        "columns": [
            {"id": "cmp-name", "name": "Scenario Name", "formula": "[Scenario Log Book/Scenario Name]"},
            {"id": "cmp-growth", "name": "Revenue Growth %",
             "formula": "[Scenario Log Book/Revenue Growth %]", "format": style.INT_FMT},
            {"id": "cmp-cost", "name": "Cost Change %",
             "formula": "[Scenario Log Book/Cost Change %]", "format": style.INT_FMT},
            {"id": "cmp-projected", "name": "Projected Total",
             "formula": "Sum([Scenario Log Book/Projected Total])", "format": style.CURRENCY_FMT},
            {"id": "cmp-delta", "name": "Δ vs. Base Case",
             "formula": "Sum([Scenario Log Book/Δ vs. Base Case])", "format": style.CURRENCY_FMT},
        ],
        "xAxis": {"columnId": "cmp-name"},
        "yAxis": {"columnIds": ["cmp-projected"]},
    })

    page = {"id": "page-rolling-forecast", "name": "Rolling Forecast", "pageWidth": style.PAGE_WIDTH}

    layout = f'''<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="page-rolling-forecast">
  <Container elementId="{hdr_id}" type="grid" gridColumn="1 / 25" gridRow="1 / 4" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <Element elementId="{title_id}" gridColumn="1 / 25" gridRow="1 / 4"/>
  </Container>
  <Container elementId="{ctrl_row_id}" type="grid" gridColumn="1 / 25" gridRow="4 / 9" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <Element elementId="{ctrl_growth_id}" gridColumn="1 / 8" gridRow="1 / 5"/>
    <Element elementId="{ctrl_cost_id}" gridColumn="8 / 15" gridRow="1 / 5"/>
    <Element elementId="{ctrl_name_id}" gridColumn="15 / 20" gridRow="1 / 5"/>
    <Element elementId="{btn_save_id}" gridColumn="20 / 23" gridRow="1 / 5"/>
    <Element elementId="{btn_reset_id}" gridColumn="23 / 25" gridRow="1 / 5"/>
  </Container>
  <Container elementId="{kpi_row_id}" type="grid" gridColumn="1 / 25" gridRow="9 / 17" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <Element elementId="{kpi_preview_id}" gridColumn="1 / 7" gridRow="1 / 9"/>
    <Element elementId="{kpi_uplift_id}" gridColumn="7 / 13" gridRow="1 / 9"/>
    <Element elementId="{kpi_baseline_id}" gridColumn="13 / 19" gridRow="1 / 9"/>
    <Element elementId="{kpi_count_id}" gridColumn="19 / 22" gridRow="1 / 9"/>
    <Element elementId="{kpi_best_id}" gridColumn="22 / 25" gridRow="1 / 9"/>
  </Container>
  <Element elementId="{compare_chart_id}" gridColumn="1 / 25" gridRow="17 / 37"/>
  <Element elementId="{log_id}" gridColumn="1 / 25" gridRow="37 / 55"/>
  <Element elementId="{log_book_id}" gridColumn="1 / 25" gridRow="55 / 69"/>
  <Element elementId="{base_id}" gridColumn="1 / 25" gridRow="69 / 83"/>
  <Element elementId="{book_id}" gridColumn="1 / 25" gridRow="83 / 97"/>
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
