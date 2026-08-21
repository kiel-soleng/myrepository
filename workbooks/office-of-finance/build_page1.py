import json, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parents[2]
sql_text = (ROOT / ".claude/skills/sigma-office-of-finance/sql/budget_actuals.sql").read_text()

elements = []
def add(el):
    elements.append(el)
    return el["id"]

def cols(names, prefix):
    return [{"id": f"{prefix}{i}", "formula": f'[Custom SQL/{n}]', "name": n}
            for i, n in enumerate(names)]

BASE_COLS = ["Period Month", "Department", "Account Type", "Budget Amount", "Actual Amount"]

# Placeholders the user must fill in before POSTing — flagged clearly in the
# accompanying prompt note and in HANDOFF-style comments here.
CONN_SNOWFLAKE = "a9d45cfe-ff65-4515-8193-a7072602a1ee"   # "Snowflake" connection -> SE_INTERNAL_DB.SCHEMA_KIEL
FOLDER_ID = "6dfa8584-aa74-4de6-99cb-ecbbbba668ac"   # Papercrane Staging/Solutions/claude-roundtrip-tests

# ---- Table 1: filtered scope (KPIs, variance chart, department table) ----
tbl_id = add({
    "id": "tbl-budget-actuals",
    "kind": "table",
    "name": "Budget vs. Actual (Custom SQL)",
    "source": {"connectionId": CONN_SNOWFLAKE, "kind": "sql", "statement": sql_text},
    "columns": cols(BASE_COLS, "ba-col-"),
})

# ---- Table 2: unfiltered duplicate, trend chart only (needs full 12mo) ----
tbl_trend_id = add({
    "id": "tbl-budget-actuals-trend",
    "kind": "table",
    "name": "Budget vs. Actual — Trend (Custom SQL)",
    "source": {"connectionId": CONN_SNOWFLAKE, "kind": "sql", "statement": sql_text},
    "columns": cols(BASE_COLS, "ba-trend-col-"),
})

# Column id lookups on tbl-budget-actuals (ba-col-0..4 = Period Month, Department, Account Type, Budget Amount, Actual Amount)
COL_PERIOD, COL_DEPT, COL_ACCTTYPE, COL_BUDGET, COL_ACTUAL = [f"ba-col-{i}" for i in range(5)]
TCOL_PERIOD, TCOL_DEPT, TCOL_ACCTTYPE, TCOL_BUDGET, TCOL_ACTUAL = [f"ba-trend-col-{i}" for i in range(5)]

# ---- Header container: title + fiscal-period control ----
hdr_id = add({"id": "container-header", "kind": "container"})
title_id = add({
    "id": "text-page-title",
    "kind": "text",
    "body": "## **FP&A Budget vs. Actual & Variance — FY26** *(swap fiscal period label per prospect)*",
    "verticalAlign": "middle",
})
ctrl_period_id = add({
    "kind": "control",
    "id": "ctrl-period",
    "controlId": "OOF-Period",
    "controlType": "list",
    "name": "Period",
    "mode": "include",
    "selectionMode": "single",
    "values": [],
    "source": {"kind": "source", "source": {"kind": "table", "elementId": tbl_id}, "columnId": COL_PERIOD},
    "filters": [{"source": {"kind": "table", "elementId": tbl_id}, "columnId": COL_PERIOD}],
})

# ---- KPI row container ----
kpi_row_id = add({"id": "container-kpi-row", "kind": "container"})

def kpi(id_, name, formula):
    return add({
        "id": id_,
        "kind": "kpi-chart",
        "name": name,
        "source": {"kind": "table", "elementId": tbl_id},
        "columns": [
            {"id": f"{id_}-period", "name": "Period Month", "formula": f"[Custom SQL/Period Month]"},
            {"id": f"{id_}-value", "name": name, "formula": formula},
        ],
        # `value.columnId`, not `value.id` — reference/specification/kpis.md,
        # verified 2026-07-02 against 26 harvested KPIs.
        "value": {"columnId": f"{id_}-value"},
    })

kpi_budget_id = kpi("kpi-total-budget", "Total Budget", f'Sum([Custom SQL/Budget Amount])')
kpi_actual_id = kpi("kpi-total-actual", "Total Actual", f'Sum([Custom SQL/Actual Amount])')
kpi_var_dollar_id = kpi("kpi-variance-dollar", "Variance $", f'Sum([Custom SQL/Actual Amount]) - Sum([Custom SQL/Budget Amount])')
kpi_var_pct_id = kpi("kpi-variance-pct", "Variance %",
    f'(Sum([Custom SQL/Actual Amount]) - Sum([Custom SQL/Budget Amount])) / Sum([Custom SQL/Budget Amount])')

# ---- Variance-by-department bar chart (waterfall substitute — see note) ----
# Passthrough mandate (reference/conventions.md -> "Passthrough mandate" +
# drill-down corollary): copy the full source-table column set onto the
# viz, not just the x/y encoding columns, or right-click drill-down has
# nowhere to go and validate-spec.py's passthrough-coverage check fails.
var_chart_id = add({
    "id": "bar-variance-by-department",
    "kind": "bar-chart",
    "name": "Variance $ by Department",
    "source": {"kind": "table", "elementId": tbl_id},
    "columns": [
        *cols(BASE_COLS, "bvd-pt-"),
        {"id": "bvd-dept", "name": "Department", "formula": "[Custom SQL/Department]"},
        {"id": "bvd-variance", "name": "Variance $",
         "formula": "Sum([Custom SQL/Actual Amount]) - Sum([Custom SQL/Budget Amount])"},
    ],
    "xAxis": {"columnId": "bvd-dept"},
    "yAxis": {"columnIds": ["bvd-variance"]},
})

# ---- Department detail table ----
dept_table_id = add({
    "id": "table-department-detail",
    "kind": "table",
    "name": "Budget vs. Actual by Department",
    "source": {"kind": "table", "elementId": tbl_id},
    "columns": [
        {"id": "dt-dept", "name": "Department", "formula": "[Custom SQL/Department]"},
        {"id": "dt-accttype", "name": "Account Type", "formula": "[Custom SQL/Account Type]"},
        {"id": "dt-budget", "name": "Budget", "formula": "Sum([Custom SQL/Budget Amount])"},
        {"id": "dt-actual", "name": "Actual", "formula": "Sum([Custom SQL/Actual Amount])"},
        {"id": "dt-variance-dollar", "name": "Variance $",
         "formula": "Sum([Custom SQL/Actual Amount]) - Sum([Custom SQL/Budget Amount])"},
        {"id": "dt-variance-pct", "name": "Variance %",
         "formula": "(Sum([Custom SQL/Actual Amount]) - Sum([Custom SQL/Budget Amount])) / Sum([Custom SQL/Budget Amount])"},
    ],
})

# ---- Trend chart: Budget vs Actual by month, trailing 12 months (unfiltered table) ----
trend_chart_id = add({
    "id": "bar-budget-actual-trend",
    "kind": "bar-chart",
    "name": "Budget vs. Actual — Trailing 12 Months",
    "source": {"kind": "table", "elementId": tbl_trend_id},
    "columns": [
        {"id": "tr-month", "name": "Month", "formula": f'[Custom SQL/Period Month]'},
        {"id": "tr-budget", "name": "Budget", "formula": "Sum([Custom SQL/Budget Amount])"},
        {"id": "tr-actual", "name": "Actual", "formula": "Sum([Custom SQL/Actual Amount])"},
    ],
    "xAxis": {"columnId": "tr-month"},
    "yAxis": {"columnIds": ["tr-budget", "tr-actual"]},
})

# Page objects are just {id, name} under the 2026-08 `document` envelope —
# elements are flat on document.elements, not nested per page (see
# reference/schema-2026-08-breaking-changes.md -> "#2 elements are FLAT").
page = {
    "id": "page-budget-variance",
    "name": "Budget vs. Actual & Variance",
}

# Layout tag names changed 2026-08: GridContainer -> Container, LayoutElement -> Element.
layout = f'''<?xml version="1.0" encoding="utf-8"?>
<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="page-budget-variance">
  <Container elementId="{hdr_id}" type="grid" gridColumn="1 / 25" gridRow="1 / 4" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <Element elementId="{title_id}" gridColumn="1 / 17" gridRow="1 / 4"/>
    <Element elementId="{ctrl_period_id}" gridColumn="17 / 25" gridRow="1 / 4"/>
  </Container>
  <Container elementId="{kpi_row_id}" type="grid" gridColumn="1 / 25" gridRow="4 / 12" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <Element elementId="{kpi_budget_id}" gridColumn="1 / 7" gridRow="1 / 9"/>
    <Element elementId="{kpi_actual_id}" gridColumn="7 / 13" gridRow="1 / 9"/>
    <Element elementId="{kpi_var_dollar_id}" gridColumn="13 / 19" gridRow="1 / 9"/>
    <Element elementId="{kpi_var_pct_id}" gridColumn="19 / 25" gridRow="1 / 9"/>
  </Container>
  <Element elementId="{var_chart_id}" gridColumn="1 / 25" gridRow="12 / 26"/>
  <Element elementId="{dept_table_id}" gridColumn="1 / 25" gridRow="26 / 40"/>
  <Element elementId="{trend_chart_id}" gridColumn="1 / 25" gridRow="40 / 54"/>
  <Element elementId="{tbl_id}" gridColumn="1 / 25" gridRow="54 / 68"/>
  <Element elementId="{tbl_trend_id}" gridColumn="1 / 25" gridRow="68 / 82"/>
</Page>'''

spec = {
    "name": "Office of Finance — Budget vs. Actual & Variance (DRAFT)",
    "folderId": FOLDER_ID,
    "document": {
        "schemaVersion": 1,
        "kind": "workbook",
        "elements": elements,
        "pages": [page],
        "layout": layout,
    },
}

out = ROOT / "workbooks" / "office-of-finance" / "iterations"
out.mkdir(parents=True, exist_ok=True)
ts = datetime.datetime.now().strftime("%Y%m%d-%H%M")
outfile = out / f"{ts}-page1-budget-variance.json"
outfile.write_text(json.dumps(spec, indent=2))
print("wrote", outfile)
