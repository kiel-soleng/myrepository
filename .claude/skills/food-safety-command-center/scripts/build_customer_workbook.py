#!/usr/bin/env python3
"""
build_customer_workbook.py — end-to-end orchestrator: customer name in,
published demo workbook out.

Phases (each independently runnable via --phase, for debugging):
  generate  -> generate_demo_data.py CSVs into <out-dir>/seed-data
  brand     -> apply_branding.py + inject 10 new input-table element
               stubs (one per warehouse-backed table) into the spec
  create    -> POST the branded+stubbed spec, save workbookId/url
  upload    -> log in (sigma_session), paste every CSV into its table
               (10 new stubs + 6 pre-existing genuine input tables)
  rewire    -> GET the live spec, repoint the 20 consumer elements at
               the new data (14 direct table-kind repoints, 6 Custom-SQL
               dedup-CTE rewrites preserving the MAX(date)-relative
               period pattern), strip system columns, PUT
  verify    -> scripts/verify-workbook.sh style compiled-SQL sweep
  publish   -> Playwright Publish
  all       -> every phase in order

State is kept in <out-dir>/state.json between phases so you can re-run
a single phase after fixing something, without repeating earlier ones.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
EXEMPLAR_PATH = os.path.join(SCRIPT_DIR, "..", "examples", "chipotle-exemplar-spec.json")
CONNECTION_ID = "9e79f38b-a310-405c-aad9-72f762ac6ff1"

import sigma_session  # noqa: E402
import input_table_upload as itu  # noqa: E402

import importlib.util as _ilu
_vs_spec = _ilu.spec_from_file_location("validate_spec", os.path.join(REPO_ROOT, "scripts", "validate-spec.py"))
validate_spec = _ilu.module_from_spec(_vs_spec)
_vs_spec.loader.exec_module(validate_spec)

# ---------------------------------------------------------------------------
# Schema for the 10 warehouse-backed tables, confirmed against the live
# SE_INTERNAL_DB.SCHEMA_KIEL.* schema via list-table-columns.sh (2026-09-28).
# `name` is the Title Case form Sigma auto-derives for warehouse-table
# columns -- giving our new input-table columns the SAME explicit `name`
# means every existing consumer formula's bare self-reference
# ([TABLE_NAME/Friendly Column Name]) keeps resolving unchanged; only the
# `source` and the element's own top-level `name` (used by OTHER elements
# to address it) need to change.
TABLE_SCHEMAS = {
    "RESTAURANTS": [
        ("RESTAURANT_ID", "text", "Restaurant Id"),
        ("NAME", "text", "Name"),
        ("REGION", "text", "Region"),
        ("FRANCHISE_OWNER", "text", "Franchise Owner"),
        ("ADDRESS", "text", "Address"),
        ("OPENED_DATE", "datetime", "Opened Date"),
    ],
    "RISK_SCORES": [
        ("RESTAURANT_ID", "text", "Restaurant Id"),
        ("CALC_DATE", "datetime", "Calc Date"),
        ("RISK_SCORE", "number", "Risk Score"),
        ("RISK_TIER", "text", "Risk Tier"),
        ("DRIVER_SUMMARY", "text", "Driver Summary"),
    ],
    "FOOD_SAFETY_AUDITS": [
        ("AUDIT_ID", "text", "Audit Id"),
        ("RESTAURANT_ID", "text", "Restaurant Id"),
        ("AUDIT_DATE", "datetime", "Audit Date"),
        ("AUDITOR", "text", "Auditor"),
        ("CATEGORY", "text", "Category"),
        ("SCORE", "number", "Score"),
        ("PASS_FAIL", "text", "Pass Fail"),
        ("SEVERITY", "text", "Severity"),
    ],
    "ACTION_ITEMS": [
        ("ACTION_ID", "text", "Action Id"),
        ("RESTAURANT_ID", "text", "Restaurant Id"),
        # id is OPENED_AT, not CREATED_AT -- the latter collides with
        # Sigma input-tables' own reserved system column of that name
        # (see generate_demo_data.py's matching comment).
        ("OPENED_AT", "datetime", "Created At"),
        ("ISSUE_SUMMARY", "text", "Issue Summary"),
        ("ASSIGNED_TO", "text", "Assigned To"),
        ("DUE_DATE", "datetime", "Due Date"),
        ("STATUS", "text", "Status"),
        ("PRIORITY", "text", "Priority"),
    ],
    "ACTION_LOG": [
        ("LOG_ID", "text", "Log Id"),
        ("ACTION_ID", "text", "Action Id"),
        ("COMPLETED_BY", "text", "Completed By"),
        ("COMPLETED_AT", "datetime", "Completed At"),
        ("RESOLUTION_NOTES", "text", "Resolution Notes"),
        ("ACKNOWLEDGMENT_FLAG", "text", "Acknowledgment Flag"),
        ("EVIDENCE_URL", "text", "Evidence Url"),
    ],
    "TASKS": [
        ("TASK_ID", "text", "Task Id"),
        ("TASK_NAME", "text", "Task Name"),
        ("FREQUENCY", "text", "Frequency"),
        ("CATEGORY", "text", "Category"),
    ],
    "TASK_COMPLETIONS": [
        ("COMPLETION_ID", "text", "Completion Id"),
        ("TASK_ID", "text", "Task Id"),
        ("RESTAURANT_ID", "text", "Restaurant Id"),
        ("EMPLOYEE_ID", "text", "Employee Id"),
        ("COMPLETED_AT", "datetime", "Completed At"),
        ("STATUS", "text", "Status"),
    ],
    "EMPLOYEES": [
        ("EMPLOYEE_ID", "text", "Employee Id"),
        ("RESTAURANT_ID", "text", "Restaurant Id"),
        ("ROLE", "text", "Role"),
        ("NAME", "text", "Name"),
    ],
    # PROMO_ELASTICITY / SALES_FORECAST_SC intentionally excluded -- see
    # _drop_promo_scenario_modeler(); generate_demo_data.py still writes
    # their CSVs (useful standalone), this orchestrator just doesn't wire
    # them into a workbook that no longer has the page that used them.
}

# Maps warehouse table name -> (new element id, new CSV filename)
NEW_ELEMENT_ID = {t: f"wh_{t.lower()}_new" for t in TABLE_SCHEMAS}
CSV_FOR_TABLE = {
    "RESTAURANTS": "RESTAURANTS.csv",
    "RISK_SCORES": "RISK_SCORES.csv",
    "FOOD_SAFETY_AUDITS": "FOOD_SAFETY_AUDITS.csv",
    "ACTION_ITEMS": "ACTION_ITEMS.csv",
    "ACTION_LOG": "ACTION_LOG.csv",
    "TASKS": "TASKS.csv",
    "TASK_COMPLETIONS": "TASK_COMPLETIONS.csv",
    "EMPLOYEES": "EMPLOYEES.csv",
}

# The 14 direct kind:"warehouse-table" elements: element id -> table name.
DIRECT_ELEMENTS = {
    "u_Qa7hZBdN": "ACTION_ITEMS",
    "qb0_cYRbmA": "ACTION_LOG",
    "e5s85TwPmD": "EMPLOYEES",
    "TsPFfqJN1U": "RESTAURANTS",
    "zJpQ8GvLnw": "RISK_SCORES",
    "qNGuj8aAef": "TASKS",
    "D3cTVBqaw7": "TASK_COMPLETIONS",
    "dr-trend-src": "RISK_SCORES",
    "dr-aud-src": "FOOD_SAFETY_AUDITS",
    "coRzP22a4w": "FOOD_SAFETY_AUDITS",
    "Qu3ZVptg2K": "FOOD_SAFETY_AUDITS",
    "RInHb2VUxA": "FOOD_SAFETY_AUDITS",
}

# The 6 genuine pre-existing input tables (kind:"empty" in the exemplar
# already) -- identified by their visible title text, not element id,
# since that's what the Playwright locate-by-title step needs.
EXISTING_INPUT_TABLES = {
    "Completion Log": "completion_log.csv",
    "Scenarios": "scenarios.csv",
    "Scenario Names": "scenario_names.csv",
    "Risk Report Profile": "risk_report_profile.csv",
    "Temperature logs": "temperature_logs.csv",
    "corrective actions": "corrective_actions.csv",
}

# The exemplar's Executive Command Center KPI row lives inside a
# type="stack" layout container (`cUKAa0I1hU`). GET-spec never emits a
# stack container's children -- confirmed this affects not just the 8
# headline KPIs but 3 separate repeated-container "card" UIs nested the
# same way (ranked risk-driver cards + two others). No fix exists for
# stack itself (scope-and-edge-cases.md); the only working path is
# dropping the orphaned elements and re-placing what's salvageable as an
# ordinary grid. We keep the 8 "current" kpi-chart elements (each already
# has its own comparisonColumn for the trend arrow -- see kpis.md's
# corrected pairing note, the "prior" twin isn't required) and drop
# everything else that the stack swallowed, including the 3 card
# repeaters -- flagged here, not silently lost.
KPI_KEEP_IDS = {
    "k-passc", "k-riskc", "k-taskc", "k-hiriskc",
    "b-HO4d6Z0Z", "RZBHxL9y85", "y_oTiXNxIM", "ZAqFAnOsr2",
}
STACK_CONTAINER_ID = "cUKAa0I1hU"

SYSTEM_COLS = {"CREATED_AT", "UPDATED_AT", "UPDATED_BY", "CREATED_BY"}


def log(msg):
    print(f"[build] {msg}", flush=True)


def _strip_system_columns(doc):
    """system column `CREATED_AT`/etc. cannot set `type` or `formula` --
    GET-spec often carries one anyway; must be stripped before every
    POST/PUT, keyed on column id, never display name."""
    stripped = 0
    for e in doc.get("elements", []):
        if e.get("kind") != "input-table":
            continue
        for c in e.get("columns", []):
            if c.get("id") in SYSTEM_COLS and ("formula" in c or "type" in c):
                c.pop("formula", None)
                c.pop("type", None)
                stripped += 1
    if stripped:
        log(f"stripped {stripped} system columns")


def state_path(out_dir):
    return os.path.join(out_dir, "state.json")


def load_state(out_dir):
    p = state_path(out_dir)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}


def save_state(out_dir, state):
    with open(state_path(out_dir), "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# Phase: generate

def phase_generate(args, state):
    seed_dir = os.path.join(args.out_dir, "seed-data")
    cmd = [
        sys.executable, os.path.join(SCRIPT_DIR, "generate_demo_data.py"),
        "--customer-name", args.customer_name,
        "--out-dir", seed_dir,
    ]
    if args.as_of:
        cmd += ["--as-of", args.as_of]
    subprocess.run(cmd, check=True)
    state["seed_dir"] = seed_dir
    return state


# ---------------------------------------------------------------------------
# Phase: brand (+ inject new input-table stubs)

def _new_table_element(table_name):
    cols = [
        {"id": col_id, "type": col_type, "name": friendly}
        for col_id, col_type, friendly in TABLE_SCHEMAS[table_name]
    ]
    return {
        "id": NEW_ELEMENT_ID[table_name],
        "kind": "input-table",
        "source": {"kind": "empty", "connectionId": CONNECTION_ID},
        "inputMode": "explore",
        "name": table_name,
        "columns": cols,
    }


def _fix_stack_containers(doc):
    """Drop every element orphaned by the type="stack" GET-spec limitation
    except the 8 headline KPIs, and re-place those 8 as ordinary grid
    children of the (converted-to-grid) former stack container."""
    root = validate_spec._parse_layout(doc.get("layout", ""))
    issues = validate_spec.issues_elements_placed(doc, root)
    orphan_ids = set()
    for level, msg in issues:
        m = re.search(r"elements \(([^,]+),", msg)
        if m:
            orphan_ids.add(m.group(1))
    drop_ids = orphan_ids - KPI_KEEP_IDS
    if not drop_ids:
        return  # nothing to fix (exemplar structure changed?)

    before = len(doc["elements"])
    doc["elements"] = [e for e in doc["elements"] if e["id"] not in drop_ids]
    log(f"dropped {before - len(doc['elements'])} elements orphaned by type=\"stack\" "
        f"(kept the 8 headline KPIs; lost 3 card repeaters -- see history.md)")


    layout = doc["layout"]
    old_tag_pattern = re.compile(
        rf'<Element elementId="{STACK_CONTAINER_ID}" type="stack".*?/>'
    )
    m = old_tag_pattern.search(layout)
    if not m:
        raise RuntimeError(f"expected stack Element tag for {STACK_CONTAINER_ID} not found")

    cols = ["1 / 4", "4 / 7", "7 / 10", "10 / 13"]
    rows = ["1 / 6", "6 / 11"]
    present_keepers = [k for k in (
        "k-passc", "k-riskc", "k-taskc", "k-hiriskc",
        "b-HO4d6Z0Z", "RZBHxL9y85", "y_oTiXNxIM", "ZAqFAnOsr2",
    ) if k not in drop_ids]
    children = []
    for i, eid in enumerate(present_keepers[:4]):
        children.append(f'    <Element elementId="{eid}" gridColumn="{cols[i]}" gridRow="{rows[0]}"/>')
    for i, eid in enumerate(present_keepers[4:8]):
        children.append(f'    <Element elementId="{eid}" gridColumn="{cols[i]}" gridRow="{rows[1]}"/>')

    new_tag = (
        f'<Container elementId="{STACK_CONTAINER_ID}" type="grid" gridColumn="1 / 19" '
        f'gridRow="5 / 16" gridTemplateColumns="repeat(12, 1fr)" gridTemplateRows="auto">\n'
        + "\n".join(children) + "\n  </Container>"
    )
    doc["layout"] = layout[:m.start()] + new_tag + layout[m.end():]


def _fix_unreachable_cta_actions(doc):
    """The exemplar's "Evidence Modal" overlay has footer.primaryCta.visible
    == "hidden" but still declares an on-primary-cta-click action. GET-spec
    harvests this fine; CREATE rejects it ("an on-primary-cta-click action
    requires footer.primaryCta.visible to not be 'hidden'") -- a GET/CREATE
    asymmetry, not something specific to this build. The action's effect
    (clear-control) is already duplicated by the same overlay's on-close
    handler, so dropping it loses nothing."""
    for ov in doc.get("overlays", []):
        modal = ov.get("modal", {})
        footer = modal.get("footer", {})
        header = modal.get("header", {})
        primary_hidden = footer.get("primaryCta", {}).get("visible") == "hidden"
        secondary_hidden = footer.get("secondaryCta", {}).get("visible") == "hidden"
        close_icon_hidden = header.get("showCloseIcon") == "hidden"
        before = len(ov.get("actions", []))
        kept = []
        for a in ov.get("actions", []):
            trigger = a.get("trigger")
            if trigger == "on-primary-cta-click" and primary_hidden:
                continue
            if trigger == "on-secondary-cta-click" and secondary_hidden:
                continue
            # on-close fires from the close icon or an Escape/backdrop
            # dismiss -- with the close icon AND both CTAs hidden, this
            # modal has no user-facing way to close at all, so its
            # on-close handler (here: a clear-control) is unreachable
            # dead config, not something CREATE will accept either.
            if trigger == "on-close" and close_icon_hidden and primary_hidden and secondary_hidden:
                continue
            kept.append(a)
        ov["actions"] = kept
        if len(kept) != before:
            log(f"dropped {before - len(kept)} unreachable action(s) on overlay '{ov.get('name')}'")


def _fix_comparison_without_column(doc):
    """The exemplar's "Danger Zone" KPI (y_oTiXNxIM) has no natural
    period-scoped prior value, so its `comparison` block was never wired
    to a `comparisonColumn` -- harmless in GET-spec, rejected at CREATE
    with "requires a comparison column or period comparison on the KPI"."""
    for e in doc.get("elements", []):
        if e.get("kind") == "kpi-chart" and "comparison" in e and "comparisonColumn" not in e:
            e.pop("comparison")
            log(f"dropped comparison block with no comparisonColumn on '{e['id']}'")


def _fix_waterfall_end_total(doc):
    """waterfallShape.endTotal only validates at CREATE time when the
    chart has split-by or multiple y-axis series -- the exemplar's single-
    series waterfall (Promo Scenario Modeler) has neither. GET-spec
    harvests the label fine; CREATE rejects it."""
    for e in doc.get("elements", []):
        if e.get("kind") != "waterfall-chart":
            continue
        shape = e.get("waterfallShape", {})
        y_axis = e.get("yAxis", {})
        has_split = bool(e.get("splitBy") or e.get("groupBy"))
        multi_series = len(y_axis.get("columnIds", [])) > 1
        if "endTotal" in shape and not (has_split or multi_series):
            shape.pop("endTotal")
            log(f"dropped unsupported waterfallShape.endTotal on '{e['id']}' (single-series)")


def _fix_dangling_sort_refs(doc):
    """A `sort[]` entry referencing a columnId no longer in that element's
    own `columns[]` -- a stale reference to a column deleted from the
    element at some point in its Sigma UI history. GET-spec harvests it
    as-is; CREATE rejects it ("references column ... which is not
    declared in columns"). Drop the stale entries."""
    for e in doc.get("elements", []):
        sort = e.get("sort")
        if not sort:
            continue
        valid_ids = {c.get("id") for c in e.get("columns", [])}
        kept = [s for s in sort if s.get("columnId") in valid_ids]
        if len(kept) != len(sort):
            log(f"dropped {len(sort) - len(kept)} dangling sort ref(s) on '{e['id']}'")
            e["sort"] = kept


_DEAD_KPI_COLUMNS = {
    # 3 of the 8 kept headline KPIs each carry copy-paste leftover
    # column(s) referenced by neither `value.columnId` nor
    # `comparisonColumn` -- confirmed by inspecting each KPI's own
    # value/comparisonColumn fields against its columns[] -- whose
    # formulas reference a bracket prefix/column-id combo that was
    # apparently never resolvable even on the live workbook (a raw
    # internal column id like "xa-period"/"xr-period"/"xt-id" used
    # where a real column *name* belongs, under the wrong table's
    # self-reference name to boot). Harmless there because the result
    # is never displayed; CREATE recompiles every formula (GET never
    # did) and fails on them with "Dependency not found". Since none
    # are used, drop them outright rather than guess at a reference
    # that was apparently never valid in the first place.
    "b-HO4d6Z0Z": {"k-passcv"},        # TASK MISS RATE -- dead "AUDIT PASS RATE" column
    "y_oTiXNxIM": {"k-hiriskcv", "k-hiriskcc"},  # DANGER ZONE -- dead "HIGH-RISK STORES" columns
    "ZAqFAnOsr2": {"k-taskcv", "k-taskcc"},      # RISK TREND -- dead task-feed columns
}


def _fix_dead_kpi_columns(doc):
    for e in doc.get("elements", []):
        dead = _DEAD_KPI_COLUMNS.get(e["id"])
        if not dead:
            continue
        before = len(e.get("columns", []))
        e["columns"] = [c for c in e.get("columns", []) if c.get("id") not in dead]
        dropped = before - len(e["columns"])
        if dropped:
            log(f"dropped {dropped} dead unused column(s) {sorted(dead)} from KPI '{e['id']}' "
                f"-- never-valid formula(s), never displayed")


def _fix_dangling_agent_datasources(doc):
    """Any agent dataSources[] entry whose elementId no longer exists --
    whether from our own stack-container drop or a pre-existing dangling
    reference in the exemplar itself -- fails CREATE with "references
    unknown element". Drop them; a chat agent losing one dataSource out
    of many is harmless, unlike losing the element itself.

    CREATE also cross-checks the other direction: every `@dataSource("id")`
    mentioned inline in an agent's own instructions text must have a
    matching dataSources[] entry ("referenced data source ... is not
    configured for this agent"). Some of those inline mentions
    (`dr-bar-task`, `dr-bar-cat` in the exemplar) were never backed by a
    real element at all -- a pre-existing gap, not something we caused.
    Strip the whole bullet line mentioning any @dataSource id that isn't
    (or is no longer) in dataSources[]."""
    valid_ids = {e["id"] for e in doc.get("elements", [])}
    for agent in doc.get("agents", []):
        ds = agent.get("dataSources")
        if ds:
            kept = [d for d in ds if d.get("elementId") in valid_ids]
            if len(kept) != len(ds):
                log(f"dropped {len(ds) - len(kept)} dangling agent dataSource ref(s) on '{agent.get('name')}'")
                agent["dataSources"] = kept
        else:
            kept = []

        configured_ids = {d.get("elementId") for d in kept}
        instructions = agent.get("instructions", "")
        if not instructions:
            continue
        lines = instructions.split("\n")
        new_lines = []
        for line in lines:
            mentioned = re.findall(r'@dataSource\("([^"]+)"\)', line)
            if mentioned and not all(m in configured_ids for m in mentioned):
                log(f"stripped instructions line referencing unconfigured dataSource "
                    f"on '{agent.get('name')}': {mentioned}")
                continue
            new_lines.append(line)
        agent["instructions"] = "\n".join(new_lines)


_PASSTHROUGH_FORMULA_RE = re.compile(r'^\[[^/\[\]]+/([^\[\]]+)\]$')


def _fix_linked_table_passthrough_names(doc):
    """`kind: "linked"` input-tables (the modal-backing tables cloned from
    ACTION_ITEMS_LIVE for the Acknowledgement/Re-Open modals, etc.) carry
    columns with `name: None` whose formula is a pure passthrough of a
    source column (e.g. `[ACTION_ITEMS_LIVE/Restaurant]`). A bare
    same-element formula resolves fine without a `name`, but *other*
    elements' text bindings cross-reference these columns by name (e.g.
    the Acknowledgement Modal body: `{{[Open Items for Acknowledgement
    Modal/Restaurant]}}`), and CREATE fails those with "Dependency not
    found" when the target column has no name to match against. Restore
    the obvious name (the formula's own passthrough target) for every
    such column, skipping any that would collide with a name already
    used elsewhere on the same element."""
    count = 0
    for e in doc.get("elements", []):
        if (e.get("source") or {}).get("kind") != "linked":
            continue
        existing_names = {c.get("name") for c in e.get("columns", []) if c.get("name")}
        for c in e.get("columns", []):
            if c.get("name"):
                continue
            m = _PASSTHROUGH_FORMULA_RE.match(c.get("formula") or "")
            if m and m.group(1) not in existing_names:
                c["name"] = m.group(1)
                existing_names.add(m.group(1))
                count += 1
    if count:
        log(f"restored {count} passthrough column name(s) on linked input-table(s) "
            f"(needed for cross-element text-binding self-references)")


def _fix_dangling_insert_rows_columns(doc):
    """An `insert-rows`/`update-rows` effect -- whether an agent tool step
    or an ordinary element/overlay button action -- hardcodes a values{}
    map keyed by target-table column id. Pre-existing stale keys here
    (e.g. the exemplar's "Food Safety Risk Analyst" -> "Create Risk
    Profile" agent tool references two column ids that no longer exist
    on the Risk Report Profile table; the "Complete Task" button's
    insert-rows into the Completion Log references a stale id for
    "Is Overdue" that's since been regenerated under a new id --
    presumably left over from a since-renamed/removed column in both
    cases) fail CREATE with "bad column: <id>". Drop any values{} key
    not present in the target table's current columns."""
    byid = {e["id"]: e for e in doc.get("elements", [])}

    def fix_effects(effects, label):
        for eff in effects or []:
            if eff.get("effect") not in ("insert-rows", "update-rows"):
                continue
            table = byid.get(eff.get("tableElementId"))
            valid_cols = {c["id"] for c in table.get("columns", [])} if table else set()
            values = eff.get("values", {})
            bad = [k for k in values if k not in valid_cols]
            if bad:
                for k in bad:
                    del values[k]
                log(f"dropped {len(bad)} dangling {eff['effect']} column ref(s) on {label}: {bad}")

    for agent in doc.get("agents", []):
        for tool in agent.get("tools", []):
            for step in tool.get("steps", []):
                if step.get("kind") == "effect":
                    fix_effects([step], f"agent '{agent.get('name')}' -> tool '{tool.get('name')}'")

    for e in doc.get("elements", []):
        for a in e.get("actions", []):
            fix_effects(a.get("effects"), f"element '{e['id']}' action '{a.get('id')}'")
    for ov in doc.get("overlays", []):
        for a in ov.get("actions", []):
            fix_effects(a.get("effects"), f"overlay '{ov.get('id')}' action '{a.get('id')}'")


_HIDDEN_TABLE_SELF_REF_TEXT = {
    # Hidden SQL-source tables whose GET-spec round-trip dropped the
    # `name.text` key, leaving only `{"visibility": "hidden"}` --
    # CREATE fails with "Dependency not found: '<lowercased name>/<col>'"
    # because every OTHER element's formulas self-reference this table
    # by name (e.g. "[Risk Feed/Period Name]", 40+ call sites) and the
    # server has no string to resolve against. `xt-audits`/`xt-tasks`
    # (same pattern, not hidden) kept their `name` as a plain string, so
    # this only bit the hidden ones. Restoring the text the rest of the
    # doc already assumes fixes it without touching any formula.
    "xt-risk": "Risk Feed",
    "lSibaPm496": "Risk Feed",
}


def _extract_container_block(layout, element_id):
    """Depth-aware extraction of a <Container elementId="..."> ... </Container>
    block (handles nested Containers inside it, unlike a naive non-greedy
    regex which would stop at the first inner </Container>). Returns
    (start, end, block) or None if not found as a non-self-closing tag."""
    m = re.search(rf'<Container[^>]*elementId="{re.escape(element_id)}"[^>]*>', layout)
    if not m:
        return None
    pos = m.end()
    depth = 1
    while depth > 0:
        nxt_close = layout.find("</Container>", pos)
        if nxt_close == -1:
            return None
        nxt_open_tag_end = layout.find(">", layout.find("<Container", pos)) if "<Container" in layout[pos:nxt_close] else -1
        nxt_open = layout.find("<Container", pos)
        if nxt_open != -1 and nxt_open < nxt_close and not layout[nxt_open:nxt_open_tag_end + 1].endswith("/>"):
            depth += 1
            pos = nxt_open + len("<Container")
        else:
            depth -= 1
            pos = nxt_close + len("</Container>")
    return m.start(), pos, layout[m.start():pos]


_BROKEN_REPEATED_CONTAINERS = {"QyX-4jVAZ_", "IvFnZKQx5j"}


def _drop_broken_repeated_containers(doc):
    """These two `repeated-container` elements have no `name` field at
    all in the GET-spec, yet their card-template children bind via
    `{{[<container's-implicit-name>/<col>]}}` (e.g.
    "FOOD_SAFETY_AUDITS repeated container", confirmed by walking the
    layout tree to find each container's actual children and reading
    off the exact bracket prefix they already use elsewhere in the
    doc). Setting that exact string as `name` had no effect on CREATE --
    it still fails with the identical "Dependency not found" error,
    meaning the self-reference name is resolved through some mechanism
    this spec's fields don't expose (possibly baked in from however the
    live workbook's UI originally built the repeater, not reproducible
    from a fresh POST). Unlike the type="stack" orphans, these ARE
    validly placed in layout with real nested content -- a different,
    new gap. Rather than keep guessing at an undocumented mechanism for
    a secondary card-repeater UI, drop these two groups outright (same
    tradeoff already accepted for the other 3 card repeaters lost to
    the type="stack" bug -- see history.md)."""
    layout = doc["layout"]
    all_drop_ids = set()
    for cid in _BROKEN_REPEATED_CONTAINERS:
        extracted = _extract_container_block(layout, cid)
        if not extracted:
            continue
        start, end, block = extracted
        child_ids = set(re.findall(r'elementId="([^"]+)"', block))
        all_drop_ids |= child_ids
        layout = layout[:start] + layout[end:]
    if not all_drop_ids:
        return
    doc["layout"] = layout
    before = len(doc["elements"])
    doc["elements"] = [e for e in doc["elements"] if e["id"] not in all_drop_ids]
    log(f"dropped {before - len(doc['elements'])} element(s) across "
        f"{len(_BROKEN_REPEATED_CONTAINERS)} broken repeated-container group(s) "
        f"(self-reference name unresolvable via POST -- see history.md)")


def _fix_hidden_table_self_ref_names(doc):
    """CREATE rejects `name: {"text": ..., "visibility": "hidden"}` outright
    ("cannot mix visibility: 'hidden' with title content"), so the
    hidden+named shape the GET-spec shows for these two tables can't be
    sent back as-is. A follow-up PUT that re-hides the title (name back
    to `{"visibility": "hidden"}`, no text) was tried and fails with the
    identical "Dependency not found" error CREATE had -- confirming the
    live original's hidden state isn't reproducible via this field at
    all (whatever the GET-spec's hidden-with-no-text shape reflects, it
    isn't something a PUT can recreate from a visible-named state; GET
    quietly omitting `text` for a hidden title looks like a display-only
    simplification, not the real stored value). Accepted tradeoff: leave
    the name permanently visible. Cosmetic only (these are internal
    helper tables never meant to be looked at directly) -- see
    history.md."""
    for eid, text in _HIDDEN_TABLE_SELF_REF_TEXT.items():
        for e in doc.get("elements", []):
            if e["id"] == eid and e.get("name") == {"visibility": "hidden"}:
                e["name"] = text
                log(f"set visible name='{text}' on table '{eid}' (stays visible "
                    f"permanently -- re-hiding isn't reproducible via PUT, see docstring above)")


def _fix_join_base_grouping(doc):
    """`joins[].{left,right}.groupingId == "base"` rejects at CREATE with
    "Grouping not found: 'base'" -- reproduced against the untouched
    exemplar's own join (Promo Scenario Modeler), so this is a pre-
    existing GET/CREATE asymmetry, not something our repoints cause.
    "base" is never a real user-defined groupings[] entry (those have
    random ids, e.g. "aK87xPtAcU" elsewhere in the same spec) -- dropping
    the key defaults the join to the ungrouped source, which is what
    "base" was presumably meant to mean."""
    count = 0

    def scrub(obj):
        nonlocal count
        if isinstance(obj, dict):
            if obj.get("groupingId") == "base":
                obj.pop("groupingId")
                count += 1
            for v in obj.values():
                scrub(v)
        elif isinstance(obj, list):
            for v in obj:
                scrub(v)

    for e in doc.get("elements", []):
        if (e.get("source") or {}).get("kind") == "join":
            scrub(e["source"])
    if count:
        log(f"dropped {count} groupingId='base' ref(s) on join sources")


def _drop_promo_scenario_modeler(doc):
    """The Promo Scenario Modeler page turned out to depend on a whole
    additional web of tables/joins/named-groupings (SALES_FORECAST_BASE,
    plus PROMO_ELASTICITY/SALES_FORECAST_SC) that surfaced one previously-
    unknown GET/CREATE gap after another while wiring this up -- each fix
    revealed a new one. It's explicitly a secondary "what-if" tool, not
    core to the food-safety demo narrative, so rather than keep chasing
    an open-ended tail of exemplar-inherited quirks in a subsystem this
    orchestrator doesn't otherwise touch, we drop the whole page. Flagged
    here, not silently lost -- see SKILL.md's Automation status."""
    layout = doc["layout"]
    start = layout.find('id="page-scenario"')
    tag_start = layout.rfind("<Page", 0, start)
    end = layout.find("</Page>", start) + len("</Page>")
    page_block = layout[tag_start:end]
    placed_ids = set(re.findall(r'elementId="([^"]+)"', page_block))

    table_ref_ids = set()
    for e in doc["elements"]:
        blob = json.dumps(e)
        if "PROMO_ELASTICITY" in blob or "SALES_FORECAST_BASE" in blob or "SALES_FORECAST_SC" in blob:
            table_ref_ids.add(e["id"])

    dropped_agent_ids = {
        a["id"] for a in doc.get("agents", [])
        if a.get("name") in ("Promo Scenario Assistant", "Promo Scenario Analyst")
    }
    chat_ids = {e["id"] for e in doc["elements"] if e.get("agentId") in dropped_agent_ids}

    drop_ids = placed_ids | table_ref_ids | chat_ids
    before = len(doc["elements"])
    doc["elements"] = [e for e in doc["elements"] if e["id"] not in drop_ids]
    doc["pages"] = [p for p in doc["pages"] if p["id"] != "page-scenario"]
    doc["layout"] = layout[:tag_start] + layout[end:]
    doc["agents"] = [a for a in doc.get("agents", []) if a["id"] not in dropped_agent_ids]

    valid_page_ids = {p["id"] for p in doc["pages"]}
    for e in doc["elements"]:
        if e.get("kind") == "navigation" and "pageLabels" in e:
            before_n = len(e["pageLabels"])
            e["pageLabels"] = [pl for pl in e["pageLabels"] if pl.get("pageId") in valid_page_ids]
            if len(e["pageLabels"]) != before_n:
                log(f"dropped page-scenario tab from navigation element '{e['id']}'")

    # Its two popovers ("New Scenario Popover", "Scenario Comparison AI")
    # trigger off elements that just got dropped with the page.
    valid_ids = {e["id"] for e in doc["elements"]}
    overlays = doc.get("overlays", [])
    kept, dropped_overlay_ids = [], set()
    for ov in overlays:
        if "popover" in ov and ov.get("popover", {}).get("triggerElementId", "_") not in valid_ids | {"_"}:
            dropped_overlay_ids.add(ov["id"])
        else:
            kept.append(ov)
    doc["overlays"] = kept

    # Every overlay (modal/drawer/popover) has its own <Page id="{overlay-id}">
    # layout block, separate from doc["pages"] -- dropping the overlay entry
    # above without also dropping its Page block leaves an orphan layout
    # page with no backing overlay, which CREATE rejects as "layout
    # references unknown page '<id>'".
    if dropped_overlay_ids:
        layout = doc["layout"]
        popover_child_ids = set()
        for oid in dropped_overlay_ids:
            m = re.search(
                r'<Page[^>]+id="' + re.escape(oid) + r'"[^>]*>.*?</Page>',
                layout, re.DOTALL,
            )
            if m:
                popover_child_ids |= set(re.findall(r'elementId="([^"]+)"', m.group(0)))
                layout = layout[:m.start()] + layout[m.end():]
        doc["layout"] = layout
        # The popover's own content (a text/control/button trio, a lone
        # chat element, etc.) was placed *only* inside its now-removed
        # Page block -- nowhere else in layout -- so it must be dropped
        # from doc["elements"] too, or CREATE rejects it as "not placed
        # in layout".
        if popover_child_ids:
            before_pc = len(doc["elements"])
            doc["elements"] = [e for e in doc["elements"] if e["id"] not in popover_child_ids]
            log(f"dropped {before_pc - len(doc['elements'])} element(s) that were only placed "
                f"inside the removed popover page(s): {sorted(popover_child_ids)}")
        log(f"dropped {len(dropped_overlay_ids)} orphaned popover overlay page(s) from layout: "
            f"{sorted(dropped_overlay_ids)}")

    log(f"dropped Promo Scenario Modeler page: {before - len(doc['elements'])} elements, "
        f"2 agents (see history.md for why)")


def _fix_dangling_action_refs(doc):
    """Final generic sweep: any action effect whose `scope.controlId` or
    `control`/`elementId`/`tableElementId` points at something no longer
    in the doc (control or element, from any of the drops above) fails
    CREATE with "references unknown control/element". Drop the offending
    effect; drop the whole action if that empties its effects list --
    losing one UI convenience (e.g. a click that used to also reset some
    now-deleted page's filter) is harmless compared to blocking create."""
    valid_element_ids = {e["id"] for e in doc.get("elements", [])}
    valid_control_ids = {
        e.get("controlId") for e in doc.get("elements", [])
        if e.get("kind") == "control" and e.get("controlId")
    }

    def effect_is_valid(eff):
        scope = eff.get("scope", {})
        for key, valid_set in (
            ("controlId", valid_control_ids),
            ("elementId", valid_element_ids),
            ("tableElementId", valid_element_ids),
        ):
            ref = scope.get(key) or eff.get(key)
            if ref is not None and ref not in valid_set:
                return False
        control_ref = eff.get("control")
        if control_ref is not None and control_ref not in valid_control_ids:
            return False
        return True

    def clean_actions(actions):
        kept = []
        dropped = 0
        for a in actions or []:
            effects = a.get("effects", [])
            valid_effects = [e for e in effects if effect_is_valid(e)]
            if len(valid_effects) != len(effects):
                dropped += len(effects) - len(valid_effects)
            if valid_effects:
                a["effects"] = valid_effects
                kept.append(a)
            elif effects:
                dropped_actions[0] += 1
        return kept, dropped

    dropped_actions = [0]
    dropped_effects = 0
    for e in doc.get("elements", []):
        if "actions" in e:
            e["actions"], n = clean_actions(e["actions"])
            dropped_effects += n
    for ov in doc.get("overlays", []):
        if "actions" in ov:
            ov["actions"], n = clean_actions(ov["actions"])
            dropped_effects += n
    if dropped_effects or dropped_actions[0]:
        log(f"dropped {dropped_effects} dangling action effect(s), "
            f"{dropped_actions[0]} emptied action(s)")


def _drop_header_panel(doc):
    """The exemplar has a workbook-level header via the top-level
    panels[] array + a <Panel> layout block (logo + duplicate nav +
    decorative icons, shared across pages). scope-and-edge-cases.md
    documents this construct as unbuildable via POST/PUT at all
    ("Layout parent not found in getLayoutParentByLayoutIdOrFail") --
    the only confirmed fix is duplicating the Panel's children onto
    every visible page as ordinary elements (new ids, new action ids),
    which is a real chunk of bespoke layout surgery on its own. Given
    Sigma's native page-tab bar is independent of this custom Panel (so
    real navigation is unaffected either way), we take the cheaper of
    the two documented-safe paths here: drop panels[] and the <Panel>
    layout block outright. The customer loses the custom logo/nav-icon
    header bar; page navigation itself keeps working via Sigma's own
    tabs. Full per-page duplication remains a follow-up if a customer
    build specifically needs that header preserved."""
    panels = doc.get("panels")
    if not panels:
        return
    layout = doc["layout"]
    m = re.search(r"<Panel\b.*?</Panel>|<Panel\b[^>]*/>", layout, re.DOTALL)
    panel_block = m.group(0) if m else ""
    child_ids = set(re.findall(r'elementId="([^"]+)"', panel_block))

    doc["layout"] = layout[:m.start()] + layout[m.end():] if m else layout
    doc["panels"] = []
    before = len(doc["elements"])
    doc["elements"] = [e for e in doc["elements"] if e["id"] not in child_ids]
    log(f"dropped {len(panels)} header panel(s) + {before - len(doc['elements'])} panel-child "
        "element(s) (logo, custom nav bar, decorative icons) -- native page tabs still work "
        "for navigation; see history.md for why a full per-page duplication wasn't attempted here")


def _prune_layout_for_missing_elements(doc):
    """Final catch-all: any <Element .../> or self-closing <Container .../>
    tag whose elementId is no longer in doc["elements"] (from any of the
    drops above, on whichever page it happened to be placed) fails CREATE
    with "layout ... references unknown element". A non-self-closing
    <Container>...</Container> is left alone even if its own elementId
    was dropped elsewhere, since removing it could orphan real nested
    children -- that case hasn't come up in practice, but dropping only
    the safe self-closing form avoids guessing at nested content."""
    valid_ids = {e["id"] for e in doc["elements"]}
    layout = doc["layout"]
    pattern = re.compile(r'<(?:Element|Container)\s+elementId="([^"]+)"[^>]*/>')
    removed = 0

    def repl(m):
        nonlocal removed
        if m.group(1) in valid_ids:
            return m.group(0)
        removed += 1
        return ""

    doc["layout"] = pattern.sub(repl, layout)
    if removed:
        log(f"pruned {removed} layout tag(s) for elements dropped elsewhere")


def phase_brand(args, state):
    branded_path = os.path.join(args.out_dir, "branded-spec.json")
    cmd = [
        sys.executable, os.path.join(SCRIPT_DIR, "apply_branding.py"),
        "--input", EXEMPLAR_PATH,
        "--output", branded_path,
        "--customer-name", args.customer_name,
        "--brand-hex", args.brand_hex,
    ]
    if args.logo_url:
        cmd += ["--logo-url", args.logo_url]
    if args.compliance_url:
        cmd += ["--compliance-url", args.compliance_url]
    subprocess.run(cmd, check=True)

    with open(branded_path) as f:
        raw = json.load(f)
    doc = raw["document"] if "document" in raw else raw

    for table_name in TABLE_SCHEMAS:
        doc["elements"].append(_new_table_element(table_name))

    # Place the new stubs on the hidden "Data Model" page, stacked in a
    # simple column so layout validation is satisfied -- they're never
    # meant to be visually prominent, just reachable for the paste step.
    layout = doc["layout"]
    data_model_page_id = _find_page_id(doc, "Data Model")
    children = "\n".join(
        f'    <Element elementId="{NEW_ELEMENT_ID[t]}" gridColumn="1 / 13" '
        f'gridRow="{1000 + i * 40} / {1000 + i * 40 + 38}"/>'
        for i, t in enumerate(TABLE_SCHEMAS)
    )
    marker = f'id="{data_model_page_id}">'
    idx = layout.index(marker) + len(marker)
    doc["layout"] = layout[:idx] + "\n" + children + layout[idx:]

    _fix_stack_containers(doc)
    _fix_unreachable_cta_actions(doc)
    _fix_comparison_without_column(doc)
    _fix_waterfall_end_total(doc)
    _fix_dangling_sort_refs(doc)
    _fix_dead_kpi_columns(doc)
    _strip_system_columns(doc)
    _fix_dangling_agent_datasources(doc)
    _fix_dangling_insert_rows_columns(doc)
    _fix_linked_table_passthrough_names(doc)
    _fix_hidden_table_self_ref_names(doc)
    _drop_broken_repeated_containers(doc)
    _fix_join_base_grouping(doc)
    _drop_promo_scenario_modeler(doc)
    _drop_header_panel(doc)
    _fix_dangling_action_refs(doc)
    _prune_layout_for_missing_elements(doc)

    with open(branded_path, "w") as f:
        json.dump({"document": doc}, f)

    state["branded_path"] = branded_path
    return state


def _find_page_id(doc, name_substr):
    for p in doc["pages"]:
        if name_substr.lower() in (p.get("name") or "").lower():
            return p["id"]
    raise RuntimeError(f"no page found matching '{name_substr}'")


# ---------------------------------------------------------------------------
# Phase: create (POST)

def phase_create(args, state):
    branded_path = state["branded_path"]
    with open(branded_path) as f:
        raw = json.load(f)
    doc = raw["document"] if "document" in raw else raw
    body = {
        "name": f"{args.customer_name} Food Safety Command Center",
        "folderId": args.folder_id,
        "document": doc,
    }
    body_path = os.path.join(args.out_dir, "create-body.json")
    with open(body_path, "w") as f:
        json.dump(body, f)

    resp = _sigma_curl(["-X", "POST", "-H", "Content-Type: application/json",
                         "--data-binary", f"@{body_path}", "/v2/workbooks/spec"])
    if not resp.get("success"):
        raise RuntimeError(f"create failed: {resp}")
    workbook_id = resp["workbookId"]
    meta = _sigma_curl(["/v2/workbooks/" + workbook_id])
    state["workbook_id"] = workbook_id
    state["workbook_url"] = meta["url"]
    state["workbook_edit_url"] = meta["url"] + "/edit"
    log(f"created workbook {workbook_id} -> {meta['url']}")
    return state


def _sigma_curl(args_list):
    env_script = os.path.join(REPO_ROOT, "scripts", "api", "_env.sh")
    cmd = f"source {env_script} && sigma_curl " + " ".join(
        f"'{a}'" if not a.startswith("/v2") else f'"$SIGMA_BASE_URL{a}"'
        for a in args_list
    )
    result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, cwd=REPO_ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"sigma_curl failed: {result.stdout}\n{result.stderr}")
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Phase: upload

def _page_name_for_element_name(doc, name):
    """Which workbook page an element with this display `name` is placed
    on, by matching its elementId inside each top-level <Page> layout
    block (overlay Page blocks are skipped -- those ids aren't in
    doc["pages"])."""
    pages_by_id = {p["id"]: p["name"] for p in doc["pages"]}
    target_ids = {e["id"] for e in doc["elements"] if e.get("name") == name}
    if not target_ids:
        return None
    for m in re.finditer(r'<Page[^>]+id="([^"]+)"[^>]*>', doc["layout"]):
        pid = m.group(1)
        if pid not in pages_by_id:
            continue
        end = doc["layout"].find("</Page>", m.end())
        block = doc["layout"][m.end():end]
        if any(f'elementId="{eid}"' in block for eid in target_ids):
            return pages_by_id[pid]
    return None


def phase_upload(args, state):
    from playwright.sync_api import sync_playwright

    storage_state_path = os.path.join(args.out_dir, "storage_state.json")
    mfa_dir = os.path.join(args.out_dir, "mfa")
    if not os.path.exists(storage_state_path):
        log("logging in (this will pause for MFA if prompted)...")
        sigma_session.login(
            org=args.org,
            storage_state_path=storage_state_path,
            mfa_marker_dir=mfa_dir,
            headless=True,
        )

    with open(state["branded_path"]) as f:
        raw = json.load(f)
    doc = raw["document"] if "document" in raw else raw

    seed_dir = state["seed_dir"]
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=sigma_session.CHROMIUM_PATH,
            headless=True,
            proxy={"server": sigma_session.PROXY_SERVER} if sigma_session.PROXY_SERVER else None,
        )
        context = browser.new_context(storage_state=storage_state_path, viewport={"width": 1600, "height": 1000})
        context.grant_permissions(["clipboard-read", "clipboard-write"])
        page = context.new_page()
        page.goto(state["workbook_edit_url"], timeout=30000)
        page.wait_for_timeout(15000)  # large workbook -- initial 6s wasn't enough
        itu.dismiss_out_of_date_dialog_if_present(page)

        current_page = None

        def goto_table(title):
            nonlocal current_page
            target = _page_name_for_element_name(doc, title)
            if target and target != current_page:
                itu.switch_to_page(page, target)
                current_page = target

        for table_name in TABLE_SCHEMAS:
            goto_table(table_name)
            csv_path = os.path.join(seed_dir, CSV_FOR_TABLE[table_name])
            count = itu.paste_csv_into_table(page, table_name, csv_path)
            log(f"{table_name}: {count} rows")

        for title, csv_name in EXISTING_INPUT_TABLES.items():
            goto_table(title)
            csv_path = os.path.join(seed_dir, csv_name)
            count = itu.paste_csv_into_table(page, title, csv_path)
            log(f"{title}: {count} rows")

        context.storage_state(path=storage_state_path)
        browser.close()

    state["uploaded"] = True
    return state


# ---------------------------------------------------------------------------
# Phase: rewire

def _repoint_warehouse_table_refs(doc):
    """DIRECT_ELEMENTS only covers the 12 elements whose *own* top-level
    `source` is `kind:"table"`-shaped. A sweep of every remaining element
    found 5 more warehouse-table references DIRECT_ELEMENTS never
    touches, in two different shapes: `kind:"join"` sources (4 elements:
    dr-task-src, dr-store, KPbGUYrwFF, ac-items -- each joining 2-3
    warehouse tables under `joins[].left/right` + `primarySource`) and a
    control's list-filter source (`E7tKc63qdS`, shape `{kind:"source",
    source:{kind:"warehouse-table",...}, columnId}`). Left unrepointed,
    these would keep showing the original Chipotle exemplar's data
    instead of the new customer's. Recursively replace any
    `{"kind":"warehouse-table",...,"path":[...,TABLE_NAME]}` dict,
    wherever nested, with `{"kind":"table","elementId":<new stub>}` --
    genuinely nested resolution: this needs the MUTATED input-table
    equivalent, but on this workbook type only a "table" source carries
    resolvable identity, so `{kind:"table", elementId}` is the right
    generic replacement regardless of where in the tree it's found."""
    count = 0

    def scrub(obj):
        nonlocal count
        if isinstance(obj, dict):
            if obj.get("kind") == "warehouse-table" and obj.get("path"):
                table_name = obj["path"][-1]
                if table_name in NEW_ELEMENT_ID:
                    obj.clear()
                    obj["kind"] = "table"
                    obj["elementId"] = NEW_ELEMENT_ID[table_name]
                    count += 1
                    return
            for v in list(obj.values()):
                scrub(v)
        elif isinstance(obj, list):
            for v in obj:
                scrub(v)

    scrub(doc.get("elements", []))
    if count:
        log(f"repointed {count} additional warehouse-table reference(s) outside DIRECT_ELEMENTS "
            f"(join sources, control list-filters) to the new customer data")


def phase_rewire(args, state):
    workbook_id = state["workbook_id"]
    live = _sigma_curl([f"/v2/workbooks/{workbook_id}/spec"])
    doc = live["document"]
    els = doc["elements"]
    byid = {e["id"]: e for e in els}

    _strip_system_columns(doc)

    # 14 direct repoints: kind:"table" at the new element, explicit own
    # `name` set to the warehouse table name so existing bare self-refs
    # ([TABLE_NAME/Friendly Column]) keep resolving unchanged.
    for eid, table_name in DIRECT_ELEMENTS.items():
        e = byid[eid]
        e["source"] = {"kind": "table", "elementId": NEW_ELEMENT_ID[table_name]}
        custom_name = e.get("name")
        if isinstance(custom_name, str) and custom_name != table_name:
            # 'RInHb2VUxA' ("Audit Detail for Risk Drivers & Trends"),
            # 'dr-trend-src' ("Risk Snapshots"), etc. -- keep the custom
            # name (referenced externally by some of them, e.g. an
            # AI-insight text element's bracket formulas) rather than
            # overwriting it to the warehouse table name as done for the
            # other 8. Do NOT also rewrite this element's own self-ref
            # formulas from table_name to custom_name -- tried that first
            # and it broke things: a bare `[table_name/Col]` formula is
            # this element's reference to its SOURCE (the new stub, whose
            # own name IS table_name), not to itself, so rewriting it to
            # the element's OWN name turns it into a bogus self-reference
            # ("Dependency not found" on a column that plainly exists).
            # The custom name only needs to be correct for how OTHER
            # elements address this one -- it has no bearing on how this
            # element addresses its own source.
            log(f"kept custom name '{custom_name}' on '{eid}' (referenced externally); "
                f"left its own self-ref formulas pointed at source table '{table_name}' unchanged")
        else:
            e["name"] = table_name

        # Cross-element bracket references (e.g. xt-risk's "Tier" column
        # doing `Lookup([RISK_SCORES/Risk Tier], ...)`, or the AI-insight
        # text above doing `[Audit Detail.../Risk Tier]`) only resolve
        # against a column's *explicit* `name` -- unlike a bare
        # same-element self-ref, which falls back to the warehouse
        # column's raw default regardless of whether `name` is set.
        # Every direct element's passthrough columns came from the
        # warehouse-table source with name=None (fine under that source
        # kind), so ALL of them need this backfill now that source is
        # kind:"table" and something elsewhere may reference them by
        # name -- not just the 4 with a custom name of their own.
        existing_names = {c.get("name") for c in e.get("columns", []) if c.get("name")}
        named = 0
        for c in e.get("columns", []):
            if c.get("name"):
                continue
            m = _PASSTHROUGH_FORMULA_RE.match(c.get("formula") or "")
            if m and m.group(1) not in existing_names:
                c["name"] = m.group(1)
                existing_names.add(m.group(1))
                named += 1
        if named:
            log(f"restored {named} passthrough column name(s) on '{eid}'")
    log(f"repointed {len(DIRECT_ELEMENTS)} direct elements")

    _repoint_warehouse_table_refs(doc)

    # 6 Custom-SQL elements: rewrite statement text to query the new
    # input tables' backing SIGDS write-tables via the proven dedup-CTE
    # pattern, preserving each element's own MAX(date)-relative period
    # logic verbatim (never a literal date).
    sigds = _discover_sigds_tables(workbook_id, els)
    _rewire_sql_elements(byid, sigds)

    body_path = os.path.join(args.out_dir, "rewire-body.json")
    with open(body_path, "w") as f:
        json.dump({"document": doc}, f)
    resp = _sigma_curl(["-X", "PUT", "-H", "Content-Type: application/json",
                         "--data-binary", f"@{body_path}", f"/v2/workbooks/{workbook_id}/spec"])
    if not resp.get("success"):
        raise RuntimeError(f"rewire PUT failed: {resp}")
    log("rewire PUT succeeded")
    return state


def _discover_sigds_tables(workbook_id, els):
    """Query each new input-table element's own compiled SQL and pull out
    the backing SE_DEMO_DB write-table name -- the only way to learn it,
    since it's assigned internally on CSV upload."""
    out = {}
    for table_name, eid in NEW_ELEMENT_ID.items():
        resp = _sigma_curl([f"/v2/workbooks/{workbook_id}/elements/{eid}/query"])
        sql = resp.get("sql", "")
        m = re.search(r'SE_DEMO_DB\.\w+\."(SIGDS_[0-9a-f_]+)"', sql)
        if not m:
            raise RuntimeError(f"could not find SIGDS table for {table_name} in: {sql[:300]}")
        out[table_name] = m.group(1)
        log(f"{table_name} -> SIGDS_{m.group(1)[6:16]}...")
    return out


def _dedup_cte(sigds_table):
    """Returns just the parenthesized CTE body -- callers prefix their
    own `<name> AS ` (e.g. "restaurants AS " + this), since the body
    doesn't need its own alias/name baked in."""
    return (
        f"(\n"
        f"  SELECT * FROM (\n"
        f"    SELECT *, ROW_NUMBER() OVER (PARTITION BY \"ID\" ORDER BY ROW_VERSION DESC) rn\n"
        f"    FROM SE_DEMO_DB.PAPERCRANE_WRITE.\"{sigds_table}\"\n"
        f"  ) WHERE rn = 1 AND TOMBSTONE_VERSION IS NULL\n"
        f")"
    )


def _rewire_sql_elements(byid, sigds):
    r, ri, a, ac, e = (sigds["RESTAURANTS"], sigds["RISK_SCORES"], sigds["ACTION_ITEMS"],
                       sigds["ACTION_LOG"], sigds["EMPLOYEES"])
    audits = sigds["FOOD_SAFETY_AUDITS"]
    tasks_completions = sigds["TASK_COMPLETIONS"]

    xt_risk_sql = (
        f"WITH restaurants AS {_dedup_cte(r)},\n"
        f"risk AS {_dedup_cte(ri)},\n"
        f"m AS (SELECT MAX(CALC_DATE) maxd FROM risk)\n"
        f"SELECT s.RESTAURANT_ID, s.CALC_DATE, s.RISK_SCORE, s.RISK_TIER, s.DRIVER_SUMMARY,\n"
        f"  r.REGION, UPPER(TRIM(RIGHT(TRIM(r.ADDRESS),2))) AS STATE, r.NAME AS RESTAURANT,\n"
        f"  CASE WHEN s.CALC_DATE=(SELECT maxd FROM m) THEN 'Current Week'\n"
        f"       WHEN s.CALC_DATE=DATEADD('week',-1,(SELECT maxd FROM m)) THEN 'Prior Week' END AS PERIOD_NAME\n"
        f"FROM risk s LEFT JOIN restaurants r ON s.RESTAURANT_ID=r.RESTAURANT_ID"
    )
    for eid in ("xt-risk", "lSibaPm496"):
        byid[eid]["source"]["statement"] = xt_risk_sql
        byid[eid]["source"]["connectionId"] = CONNECTION_ID

    xt_audits_sql = (
        f"WITH restaurants AS {_dedup_cte(r)},\n"
        f"audits AS {_dedup_cte(audits)},\n"
        f"m AS (SELECT MAX(DATE_TRUNC('month',AUDIT_DATE)) maxm FROM audits)\n"
        f"SELECT a.AUDIT_ID, a.AUDIT_DATE, DATE_TRUNC('month',a.AUDIT_DATE) AS AUDIT_MONTH,\n"
        f"  a.PASS_FAIL, a.CATEGORY, a.SEVERITY, a.SCORE, r.REGION,\n"
        f"  UPPER(TRIM(RIGHT(TRIM(r.ADDRESS),2))) AS STATE, r.NAME AS RESTAURANT,\n"
        f"  CASE WHEN DATE_TRUNC('month',a.AUDIT_DATE)=(SELECT maxm FROM m) THEN 'Current Month'\n"
        f"       WHEN DATE_TRUNC('month',a.AUDIT_DATE)=DATEADD('month',-1,(SELECT maxm FROM m)) THEN 'Prior Month' END AS PERIOD_NAME\n"
        f"FROM audits a LEFT JOIN restaurants r ON a.RESTAURANT_ID=r.RESTAURANT_ID"
    )
    byid["xt-audits"]["source"]["statement"] = xt_audits_sql

    xt_tasks_sql = (
        f"WITH restaurants AS {_dedup_cte(r)},\n"
        f"completions AS {_dedup_cte(tasks_completions)},\n"
        f"m AS (SELECT MAX(DATE_TRUNC('month',COMPLETED_AT)) maxm FROM completions)\n"
        f"SELECT t.COMPLETION_ID, t.STATUS, DATE_TRUNC('month',t.COMPLETED_AT) AS COMP_MONTH, r.REGION,\n"
        f"  CASE WHEN DATE_TRUNC('month',t.COMPLETED_AT)=(SELECT maxm FROM m) THEN 'Current Month'\n"
        f"       WHEN DATE_TRUNC('month',t.COMPLETED_AT)=DATEADD('month',-1,(SELECT maxm FROM m)) THEN 'Prior Month' END AS PERIOD_NAME\n"
        f"FROM completions t LEFT JOIN restaurants r ON t.RESTAURANT_ID=r.RESTAURANT_ID"
    )
    byid["xt-tasks"]["source"]["statement"] = xt_tasks_sql

    action_items_live_sql = (
        f"WITH restaurants AS {_dedup_cte(r)},\n"
        f"employees AS {_dedup_cte(e)},\n"
        f"action_items AS {_dedup_cte(a)},\n"
        f"action_log AS {_dedup_cte(ac)},\n"
        f"risk AS {_dedup_cte(ri)},\n"
        # "today" anchors to RISK_SCORES' own MAX(date), matching the
        # exemplar's original pattern and every other rewritten element
        # here -- not to action_items' own OPENED_AT, which would make
        # the overdue/days-open math wobble with whatever a particular
        # item's age happens to be instead of a single stable reference
        # date shared network-wide.
        f"m AS (SELECT MAX(CALC_DATE) today FROM risk),\n"
        f"gm AS (SELECT RESTAURANT_ID, MAX(NAME) AS GM FROM employees WHERE ROLE='General Manager' GROUP BY RESTAURANT_ID)\n"
        f"SELECT a.ACTION_ID, a.RESTAURANT_ID, r.NAME AS RESTAURANT, r.REGION,\n"
        f"  a.ISSUE_SUMMARY, a.PRIORITY, a.STATUS, COALESCE(a.ASSIGNED_TO, g.GM, 'Unassigned') AS ASSIGNED_TO,\n"
        f"  a.OPENED_AT AS CREATED_AT, a.DUE_DATE,\n"
        f"  lg.COMPLETED_BY, lg.COMPLETED_AT, lg.RESOLUTION_NOTES, lg.ACKNOWLEDGMENT_FLAG,\n"
        f"  m.today AS AS_OF,\n"
        f"  CASE WHEN a.STATUS <> 'Complete' AND a.DUE_DATE < m.today THEN TRUE ELSE FALSE END AS IS_OVERDUE,\n"
        f"  DATEDIFF('day', a.OPENED_AT, m.today) AS DAYS_OPEN,\n"
        f"  DATEDIFF('day', a.OPENED_AT, lg.COMPLETED_AT) AS DAYS_TO_RESOLVE\n"
        f"FROM action_items a CROSS JOIN m\n"
        f"LEFT JOIN restaurants r ON a.RESTAURANT_ID = r.RESTAURANT_ID\n"
        f"LEFT JOIN action_log lg ON a.ACTION_ID = lg.ACTION_ID\n"
        f"LEFT JOIN gm g ON g.RESTAURANT_ID = a.RESTAURANT_ID"
    )
    for eid in ("swKkSOIq4q", "9x3b501JzN"):
        if eid in byid:
            byid[eid]["source"]["statement"] = action_items_live_sql


# ---------------------------------------------------------------------------
# Phase: verify / publish

def phase_verify(args, state):
    script = os.path.join(REPO_ROOT, "scripts", "api", "verify-workbook.sh")
    result = subprocess.run(["bash", script, state["workbook_id"]], capture_output=True, text=True, cwd=REPO_ROOT)
    print(result.stdout[-4000:])
    if result.returncode != 0:
        log("verify-workbook.sh reported failures -- see output above")
    return state


def phase_publish(args, state):
    from playwright.sync_api import sync_playwright

    storage_state_path = os.path.join(args.out_dir, "storage_state.json")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=sigma_session.CHROMIUM_PATH,
            headless=True,
            proxy={"server": sigma_session.PROXY_SERVER} if sigma_session.PROXY_SERVER else None,
        )
        context = browser.new_context(storage_state=storage_state_path, viewport={"width": 1600, "height": 1000})
        page = context.new_page()
        page.goto(state["workbook_edit_url"], timeout=30000)
        page.wait_for_timeout(6000)
        itu.dismiss_out_of_date_dialog_if_present(page)
        itu.publish(page)
        browser.close()
    log(f"published: {state['workbook_url']}")
    return state


PHASES = {
    "generate": phase_generate,
    "brand": phase_brand,
    "create": phase_create,
    "upload": phase_upload,
    "rewire": phase_rewire,
    "verify": phase_verify,
    "publish": phase_publish,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--customer-name", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--brand-hex", default="#333333")
    ap.add_argument("--logo-url", default=None)
    ap.add_argument("--compliance-url", default=None)
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--folder-id", required=True)
    ap.add_argument("--org", default="papercrane")
    ap.add_argument("--phase", default="all", choices=list(PHASES) + ["all"])
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    state = load_state(args.out_dir)

    phases = list(PHASES) if args.phase == "all" else [args.phase]
    for name in phases:
        log(f"=== phase: {name} ===")
        state = PHASES[name](args, state)
        save_state(args.out_dir, state)


if __name__ == "__main__":
    main()
