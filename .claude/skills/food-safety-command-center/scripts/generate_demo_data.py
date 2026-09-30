#!/usr/bin/env python3
"""
generate_demo_data.py — parameterized synthetic data generator for the
Food Safety Command Center workbook pattern.

Usage:
    python3 generate_demo_data.py --customer-name "Big Sky Grill" \
        --out-dir workbooks/big-sky-grill/seed-data

Deterministic by default: the RNG seed is derived from --customer-name,
so re-running for the same customer name reproduces the same demo data.
Pass --seed to override and get a different draw for the same customer.

All dates are relative to --as-of (default: today, not a literal date),
so a demo built today doesn't look stale months later — just omit
--as-of (or pass a fresh one) before every new demo run.

Outputs one CSV per table this workbook pattern needs, matching the
canonical exemplar's exact raw column names (see
reference/data-seeding.md for how each CSV gets wired into the Sigma
spec). Two families, per data-seeding.md's existing "Fix 1"/"Fix 2" split:

  Warehouse-backed tables (repointed via Custom SQL / direct table source
  during the build):
    RESTAURANTS, RISK_SCORES, FOOD_SAFETY_AUDITS, ACTION_ITEMS,
    ACTION_LOG, TASKS, TASK_COMPLETIONS, EMPLOYEES, PROMO_ELASTICITY,
    SALES_FORECAST_SC

  Input-table-backed pages (uploaded directly as new Sigma input tables):
    completion_log, scenarios, scenario_names, risk_report_profile,
    temperature_logs, corrective_actions

Column shapes for the ten warehouse-backed tables were confirmed against
the real SE_INTERNAL_DB.SCHEMA_KIEL.* schema via
`scripts/api/list-table-columns.sh` (2026-09-28) — this is the
authoritative source, not a guess from the exemplar's display formulas.
"""
import argparse
import csv
import hashlib
import os
import random
from datetime import date, datetime, timedelta

from data_pools import (
    ACTION_ITEM_ISSUES,
    ACTION_PRIORITIES,
    ACTION_STATUSES,
    AUDIT_CATEGORIES,
    AUDIT_SEVERITIES,
    CITIES,
    EMPLOYEE_ROLES,
    FIRST_NAMES,
    FRANCHISE_OWNERS,
    LAST_NAMES,
    PROMO_CHANNELS,
    PROMO_ITEMS,
    PROMO_SEGMENTS,
    RESOLUTION_NOTES,
    RISK_TIERS,
    ROOT_CAUSES,
    STREET_NAMES,
    TASK_CATALOG,
)

TASK_STATUS_DONE = "Done"
TASK_STATUS_MISSED = "Missed"
TASK_STATUS_LATE = "Late"


def week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def month_start(d: date) -> date:
    return d.replace(day=1)


def add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    return d.replace(year=y, month=m, day=1)


def risk_tier_for(score: float) -> str:
    if score >= 80:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 35:
        return "Medium"
    return "Low"


def short_code(name: str) -> str:
    letters = [c for c in name.upper() if c.isalnum()]
    words = [w for w in name.upper().split() if w]
    if len(words) >= 2:
        code = "".join(w[0] for w in words if w[0].isalnum())[:3]
    else:
        code = "".join(letters)[:3]
    return code or "STR"


class DemoDataGenerator:
    def __init__(self, customer_name, out_dir, num_stores=20, critical_stores=1,
                 as_of=None, rng=None):
        self.customer_name = customer_name
        self.out_dir = out_dir
        self.num_stores = num_stores
        self.critical_stores = critical_stores
        self.as_of = as_of or date.today()
        self.rng = rng or random.Random(0)
        self.code = short_code(customer_name)
        os.makedirs(out_dir, exist_ok=True)

        self.stores = self._build_stores()
        self.critical_ids = {s["RESTAURANT_ID"] for s in self.stores[:critical_stores]}
        self.employees_by_store = {}
        self.action_items = []

    # ---- helpers -------------------------------------------------------

    def _write_csv(self, filename, fieldnames, rows):
        path = os.path.join(self.out_dir, filename)
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for row in rows:
                w.writerow(row)
        return path

    def _build_stores(self):
        stores = []
        cities = self.rng.sample(CITIES, min(len(CITIES), self.num_stores))
        while len(cities) < self.num_stores:
            cities.append(self.rng.choice(CITIES))
        for i, (city, state, region) in enumerate(cities, start=1):
            rid = f"{self.code}{i:04d}"
            street = f"{self.rng.randint(100, 9999)} {self.rng.choice(STREET_NAMES)}"
            opened = self.as_of - timedelta(days=self.rng.randint(365, 15 * 365))
            stores.append({
                "RESTAURANT_ID": rid,
                "NAME": f"{self.customer_name} #{1000 + i}",
                "REGION": region,
                "FRANCHISE_OWNER": self.rng.choice(FRANCHISE_OWNERS),
                "ADDRESS": f"{street}, {city}, {state}",
                "OPENED_DATE": opened.isoformat(),
            })
        return stores

    def _person_name(self):
        return f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}"

    # ---- warehouse-backed tables ---------------------------------------

    def gen_restaurants(self):
        fields = ["RESTAURANT_ID", "NAME", "REGION", "FRANCHISE_OWNER", "ADDRESS", "OPENED_DATE"]
        return self._write_csv("RESTAURANTS.csv", fields, self.stores)

    def gen_employees(self):
        rows = []
        for store in self.stores:
            rid = store["RESTAURANT_ID"]
            staff = []
            gm_id = f"{rid}-E1"
            staff.append({"EMPLOYEE_ID": gm_id, "RESTAURANT_ID": rid,
                          "ROLE": "General Manager", "NAME": self._person_name()})
            n_extra = self.rng.randint(2, 3)
            for j in range(2, n_extra + 2):
                staff.append({
                    "EMPLOYEE_ID": f"{rid}-E{j}",
                    "RESTAURANT_ID": rid,
                    "ROLE": self.rng.choice(EMPLOYEE_ROLES[1:]),
                    "NAME": self._person_name(),
                })
            self.employees_by_store[rid] = staff
            rows.extend(staff)
        fields = ["EMPLOYEE_ID", "RESTAURANT_ID", "ROLE", "NAME"]
        return self._write_csv("EMPLOYEES.csv", fields, rows)

    def gen_risk_scores(self, num_weeks=13):
        rows = []
        this_monday = week_monday(self.as_of)
        for store in self.stores:
            rid = store["RESTAURANT_ID"]
            is_critical = rid in self.critical_ids
            base = self.rng.uniform(55, 75) if is_critical else self.rng.uniform(15, 45)
            for w in range(num_weeks - 1, -1, -1):
                calc_date = this_monday - timedelta(weeks=w)
                drift = self.rng.uniform(-6, 6)
                score = max(0, min(100, base + drift))
                tier = risk_tier_for(score)
                rows.append({
                    "RESTAURANT_ID": rid,
                    "CALC_DATE": calc_date.isoformat(),
                    "RISK_SCORE": round(score, 1),
                    "RISK_TIER": tier,
                    "DRIVER_SUMMARY": self._driver_summary(tier),
                })
        fields = ["RESTAURANT_ID", "CALC_DATE", "RISK_SCORE", "RISK_TIER", "DRIVER_SUMMARY"]
        return self._write_csv("RISK_SCORES.csv", fields, rows)

    def _driver_summary(self, tier):
        if tier in ("Critical", "High"):
            return self.rng.choice([
                "Elevated temperature-control failures this period.",
                "Repeated sanitation deficiencies flagged in recent audits.",
                "Multiple missed daily compliance tasks.",
                "Open corrective actions past due.",
            ])
        return self.rng.choice([
            "No significant risk drivers this period.",
            "Minor documentation gaps, low impact.",
            "Stable performance across audit categories.",
        ])

    def gen_food_safety_audits(self, lookback_days=120):
        rows = []
        aid = 1
        for store in self.stores:
            rid = store["RESTAURANT_ID"]
            is_critical = rid in self.critical_ids
            # Ensure coverage in both the current and prior calendar month.
            for month_offset in (0, -1):
                anchor = add_months(self.as_of, month_offset)
                days_in_window = 28
                n_audits = self.rng.randint(2, 4)
                for _ in range(n_audits):
                    day_offset = self.rng.randint(0, days_in_window - 1)
                    audit_date = anchor + timedelta(days=day_offset)
                    if audit_date > self.as_of:
                        audit_date = self.as_of
                    fail_chance = 0.45 if is_critical else 0.12
                    pass_fail = "Fail" if self.rng.random() < fail_chance else "Pass"
                    score = self.rng.uniform(50, 75) if pass_fail == "Fail" else self.rng.uniform(80, 100)
                    rows.append({
                        "AUDIT_ID": f"A{aid:05d}",
                        "RESTAURANT_ID": rid,
                        "AUDIT_DATE": audit_date.isoformat(),
                        "AUDITOR": self._person_name(),
                        "CATEGORY": self.rng.choice(AUDIT_CATEGORIES),
                        "SCORE": round(score, 1),
                        "PASS_FAIL": pass_fail,
                        "SEVERITY": self.rng.choice(AUDIT_SEVERITIES) if pass_fail == "Fail" else "Low",
                    })
                    aid += 1
        fields = ["AUDIT_ID", "RESTAURANT_ID", "AUDIT_DATE", "AUDITOR", "CATEGORY", "SCORE", "PASS_FAIL", "SEVERITY"]
        return self._write_csv("FOOD_SAFETY_AUDITS.csv", fields, rows)

    def gen_tasks(self):
        rows = [{"TASK_ID": f"T{i+1}", "TASK_NAME": name, "FREQUENCY": freq, "CATEGORY": cat}
                for i, (name, freq, cat) in enumerate(TASK_CATALOG)]
        fields = ["TASK_ID", "TASK_NAME", "FREQUENCY", "CATEGORY"]
        self.tasks = rows
        return self._write_csv("TASKS.csv", fields, rows)

    def gen_task_completions(self, window_days=65):
        if not hasattr(self, "tasks"):
            self.gen_tasks()
        rows = []
        cid = 1
        daily_tasks = [t for t in self.tasks if t["FREQUENCY"] == "Daily"]
        weekly_tasks = [t for t in self.tasks if t["FREQUENCY"] == "Weekly"]
        for store in self.stores:
            rid = store["RESTAURANT_ID"]
            is_critical = rid in self.critical_ids
            staff = self.employees_by_store.get(rid) or [{"EMPLOYEE_ID": f"{rid}-E1"}]
            miss_chance = 0.35 if is_critical else 0.08
            for day_offset in range(window_days):
                d = self.as_of - timedelta(days=day_offset)
                for t in daily_tasks:
                    status = self._task_status(miss_chance)
                    rows.append(self._completion_row(cid, t, rid, staff, d, status))
                    cid += 1
                if d.weekday() == 0:
                    for t in weekly_tasks:
                        status = self._task_status(miss_chance)
                        rows.append(self._completion_row(cid, t, rid, staff, d, status))
                        cid += 1
        fields = ["COMPLETION_ID", "TASK_ID", "RESTAURANT_ID", "EMPLOYEE_ID", "COMPLETED_AT", "STATUS"]
        return self._write_csv("TASK_COMPLETIONS.csv", fields, rows)

    def _task_status(self, miss_chance):
        r = self.rng.random()
        if r < miss_chance * 0.6:
            return TASK_STATUS_MISSED
        if r < miss_chance:
            return TASK_STATUS_LATE
        return TASK_STATUS_DONE

    def _completion_row(self, cid, task, rid, staff, d, status):
        return {
            "COMPLETION_ID": f"C{cid:06d}",
            "TASK_ID": task["TASK_ID"],
            "RESTAURANT_ID": rid,
            "EMPLOYEE_ID": self.rng.choice(staff)["EMPLOYEE_ID"],
            "COMPLETED_AT": datetime.combine(d, datetime.min.time()).isoformat(),
            "STATUS": status,
        }

    def gen_action_items_and_log(self, items_per_store=(3, 6)):
        item_rows = []
        log_rows = []
        aid = 1
        lid = 1
        for store in self.stores:
            rid = store["RESTAURANT_ID"]
            staff = self.employees_by_store.get(rid) or [{"EMPLOYEE_ID": f"{rid}-E1", "NAME": "Store Manager"}]
            n = self.rng.randint(*items_per_store)
            for _ in range(n):
                created = self.as_of - timedelta(days=self.rng.randint(1, 45))
                due = created + timedelta(days=self.rng.randint(3, 14))
                status = self.rng.choices(ACTION_STATUSES, weights=[0.25, 0.25, 0.5])[0]
                item_id = f"AI{aid:05d}"
                assignee = self.rng.choice(staff)
                item_rows.append({
                    "ACTION_ID": item_id,
                    "RESTAURANT_ID": rid,
                    # Named OPENED_AT, not CREATED_AT -- the latter collides
                    # with Sigma input-tables' own reserved system column of
                    # that name, which silently renames the incoming column
                    # to an internal generated alias (e.g. "FIRST_13") on
                    # upload instead of erroring, a trap for whatever SQL
                    # later reads it back by name.
                    "OPENED_AT": datetime.combine(created, datetime.min.time()).isoformat(),
                    "ISSUE_SUMMARY": self.rng.choice(ACTION_ITEM_ISSUES),
                    "ASSIGNED_TO": assignee.get("NAME", "Store Manager"),
                    "DUE_DATE": due.isoformat(),
                    "STATUS": status,
                    "PRIORITY": self.rng.choice(ACTION_PRIORITIES),
                })
                self.action_items.append({"ACTION_ID": item_id, "RESTAURANT_ID": rid,
                                           "STATUS": status, "DUE_DATE": due,
                                           "ISSUE_SUMMARY": item_rows[-1]["ISSUE_SUMMARY"]})
                if status == "Complete":
                    completed_at = due - timedelta(days=self.rng.randint(0, 3))
                    log_rows.append({
                        "LOG_ID": f"L{lid:05d}",
                        "ACTION_ID": item_id,
                        "COMPLETED_BY": assignee.get("NAME", "Store Manager"),
                        "COMPLETED_AT": datetime.combine(completed_at, datetime.min.time()).isoformat(),
                        "RESOLUTION_NOTES": self.rng.choice(RESOLUTION_NOTES),
                        "ACKNOWLEDGMENT_FLAG": self.rng.random() < 0.85,
                        "EVIDENCE_URL": "",
                    })
                    lid += 1
                aid += 1
        item_fields = ["ACTION_ID", "RESTAURANT_ID", "OPENED_AT", "ISSUE_SUMMARY", "ASSIGNED_TO", "DUE_DATE", "STATUS", "PRIORITY"]
        log_fields = ["LOG_ID", "ACTION_ID", "COMPLETED_BY", "COMPLETED_AT", "RESOLUTION_NOTES", "ACKNOWLEDGMENT_FLAG", "EVIDENCE_URL"]
        p1 = self._write_csv("ACTION_ITEMS.csv", item_fields, item_rows)
        p2 = self._write_csv("ACTION_LOG.csv", log_fields, log_rows)
        return p1, p2

    def gen_promo_elasticity(self):
        rows = []
        for seg in PROMO_SEGMENTS:
            for chan in PROMO_CHANNELS:
                for item in PROMO_ITEMS:
                    rows.append({
                        "STORE_SEGMENT": seg,
                        "CHANNEL": chan,
                        "ITEM_CATEGORY": item,
                        "UNIT_ELASTICITY": round(self.rng.uniform(0.5, 2.5), 2),
                        "BASE_MARGIN_PCT": round(self.rng.uniform(0.15, 0.4), 3),
                        "BREAKEVEN_DISCOUNT_PCT": round(self.rng.uniform(0.05, 0.25), 3),
                    })
        fields = ["STORE_SEGMENT", "CHANNEL", "ITEM_CATEGORY", "UNIT_ELASTICITY", "BASE_MARGIN_PCT", "BREAKEVEN_DISCOUNT_PCT"]
        return self._write_csv("PROMO_ELASTICITY.csv", fields, rows)

    def gen_sales_forecast(self, horizon_days=90):
        rows = []
        base = self.rng.uniform(8000, 15000)
        for series in ("Baseline", "Promo Scenario A"):
            level = base * (1.08 if series != "Baseline" else 1.0)
            for i in range(horizon_days):
                ts = self.as_of + timedelta(days=i)
                seasonal = 1 + 0.1 * ((i % 7) in (4, 5))
                forecast = level * seasonal * self.rng.uniform(0.95, 1.05)
                rows.append({
                    "SERIES": series,
                    "TS": datetime.combine(ts, datetime.min.time()).isoformat(),
                    "FORECAST": round(forecast, 2),
                    "LOWER_BOUND": round(forecast * 0.9, 2),
                    "UPPER_BOUND": round(forecast * 1.1, 2),
                })
        fields = ["SERIES", "TS", "FORECAST", "LOWER_BOUND", "UPPER_BOUND"]
        return self._write_csv("SALES_FORECAST_SC.csv", fields, rows)

    # ---- genuine Sigma input tables ------------------------------------

    def gen_completion_log(self, n=20):
        if not self.action_items:
            self.gen_action_items_and_log()
        rows = []
        sample = self.rng.sample(self.action_items, min(n, len(self.action_items)))
        for item in sample:
            store = next(s for s in self.stores if s["RESTAURANT_ID"] == item["RESTAURANT_ID"])
            due = item["DUE_DATE"]
            completed_at = due - timedelta(days=self.rng.randint(-2, 3))
            is_overdue = "Yes" if completed_at > due else "No"
            days_open = max(0, (self.as_of - due).days) if item["STATUS"] != "Complete" else 0
            days_to_resolve = max(0, (completed_at - (due - timedelta(days=7))).days)
            rows.append({
                "Action Id": item["ACTION_ID"],
                "Restaurant Id": item["RESTAURANT_ID"],
                "Region": store["REGION"],
                "Issue Summary": item["ISSUE_SUMMARY"],
                "Priority": self.rng.choice(ACTION_PRIORITIES),
                "Assigned To": self._person_name(),
                "Due Date": due.isoformat(),
                "Completed By": self._person_name() if item["STATUS"] == "Complete" else "",
                "Completed At": completed_at.isoformat() if item["STATUS"] == "Complete" else "",
                "Is Overdue": is_overdue,
                "Days Open": days_open,
                "Days to Resolve": days_to_resolve,
                "Resolution Notes": self.rng.choice(RESOLUTION_NOTES) if item["STATUS"] == "Complete" else "",
                "Root Cause": self.rng.choice(ROOT_CAUSES),
                "Corrective Action Verified?": item["STATUS"] == "Complete",
                "Photo / File Evidence": "",
                "Attestation Agreement": item["STATUS"] == "Complete",
                "Status": item["STATUS"],
            })
        fields = ["Action Id", "Restaurant Id", "Region", "Issue Summary", "Priority",
                  "Assigned To", "Due Date", "Completed By", "Completed At", "Is Overdue",
                  "Days Open", "Days to Resolve", "Resolution Notes", "Root Cause",
                  "Corrective Action Verified?", "Photo / File Evidence",
                  "Attestation Agreement", "Status"]
        return self._write_csv("completion_log.csv", fields, rows)

    def gen_scenarios(self, n=4):
        rows = []
        for i in range(n):
            start = self.as_of + timedelta(days=self.rng.randint(7, 30))
            end = start + timedelta(days=self.rng.randint(7, 21))
            rows.append({
                "Scenario Name": f"{self.customer_name} Promo {i + 1}",
                "Status": self.rng.choice(["Draft", "Submitted", "Approved"]),
                "Discount": self.rng.choice([10, 15, 20, 25]),
                "Segment": self.rng.choice(PROMO_SEGMENTS),
                "Promo Channel": self.rng.choice(PROMO_CHANNELS),
                "Item": self.rng.choice(PROMO_ITEMS),
                "Promo Start": start.isoformat(),
                "Promo End": end.isoformat(),
            })
        fields = ["Scenario Name", "Status", "Discount", "Segment", "Promo Channel", "Item", "Promo Start", "Promo End"]
        self.scenarios = rows
        return self._write_csv("scenarios.csv", fields, rows)

    def gen_scenario_names(self):
        if not hasattr(self, "scenarios"):
            self.gen_scenarios()
        rows = [{"Scenario Name": s["Scenario Name"], "Status": s["Status"]} for s in self.scenarios]
        fields = ["Scenario Name", "Status"]
        return self._write_csv("scenario_names.csv", fields, rows)

    def gen_risk_report_profile(self):
        rows = []
        this_monday = week_monday(self.as_of).isoformat()
        for store in self.stores:
            rid = store["RESTAURANT_ID"]
            is_critical = rid in self.critical_ids
            avg_risk = self.rng.uniform(55, 75) if is_critical else self.rng.uniform(15, 45)
            rows.append({
                "Restaurant Id": rid,
                "Region": store["REGION"],
                "Period": this_monday,
                "Exec Summary": f"{store['NAME']} risk posture for the week of {this_monday}.",
                "Top Drivers": self._driver_summary(risk_tier_for(avg_risk)),
                "Actions Summary": "See open action items for this location.",
                "Recommendations": "Continue daily compliance checks; review flagged categories.",
                "High RIsk Count": 1 if is_critical else 0,
                "Avg Risk Score": round(avg_risk, 1),
                "Task Miss Rate": round(self.rng.uniform(0.2, 0.4) if is_critical else self.rng.uniform(0.02, 0.1), 3),
                "Audit Failure Rate": round(self.rng.uniform(0.3, 0.5) if is_critical else self.rng.uniform(0.0, 0.15), 3),
                "Open Actions/Overdue/Completed This Week": self.rng.randint(0, 5),
                "Status": "Critical" if is_critical else "Stable",
                "Restaurant": store["NAME"],
            })
        fields = ["Restaurant Id", "Region", "Period", "Exec Summary", "Top Drivers",
                  "Actions Summary", "Recommendations", "High RIsk Count", "Avg Risk Score",
                  "Task Miss Rate", "Audit Failure Rate",
                  "Open Actions/Overdue/Completed This Week", "Status", "Restaurant"]
        return self._write_csv("risk_report_profile.csv", fields, rows)

    def gen_temperature_logs(self, days=7):
        rows = []
        units = [("Walk-in Cooler", 33, 40), ("Walk-in Freezer", -10, 0)]
        for store in self.stores[: min(5, len(self.stores))]:
            for unit_name, tmin, tmax in units:
                for day_offset in range(days):
                    d = self.as_of - timedelta(days=day_offset)
                    reading = self.rng.uniform(tmin - 3, tmax + 3)
                    status = "Pass" if tmin <= reading <= tmax else self.rng.choice(["Fail", "Check"])
                    rows.append({
                        "Unit": f"{unit_name} ({store['NAME']})",
                        "Target Min (F)": tmin,
                        "Target Max (F)": tmax,
                        "Last Reading (F)": round(reading, 1),
                        "Time Checked": datetime.combine(d, datetime.min.time()).isoformat(),
                        "Status": status,
                    })
        fields = ["Unit", "Target Min (F)", "Target Max (F)", "Last Reading (F)", "Time Checked", "Status"]
        return self._write_csv("temperature_logs.csv", fields, rows)

    def gen_corrective_actions(self, n=18):
        rows = []
        for i in range(n):
            due = self.as_of + timedelta(days=self.rng.randint(-5, 14))
            status = "Overdue" if due < self.as_of else "On Track"
            rows.append({
                "Action ID": f"CA{i + 1:04d}",
                "Issue": self.rng.choice(ACTION_ITEM_ISSUES),
                "Risk Tier": self.rng.choice(["Medium", "High"]),
                "Assigned To": self._person_name(),
                "Due Date": due.date().isoformat() if hasattr(due, "date") else due.isoformat(),
                "Due Time": f"{self.rng.randint(8, 17):02d}:00",
                "Status": status,
            })
        fields = ["Action ID", "Issue", "Risk Tier", "Assigned To", "Due Date", "Due Time", "Status"]
        return self._write_csv("corrective_actions.csv", fields, rows)

    def generate_all(self):
        paths = []
        paths.append(self.gen_restaurants())
        paths.append(self.gen_employees())
        paths.append(self.gen_risk_scores())
        paths.append(self.gen_food_safety_audits())
        self.gen_tasks()
        paths.append(os.path.join(self.out_dir, "TASKS.csv"))
        paths.append(self.gen_task_completions())
        paths.extend(self.gen_action_items_and_log())
        paths.append(self.gen_promo_elasticity())
        paths.append(self.gen_sales_forecast())
        paths.append(self.gen_completion_log())
        self.gen_scenarios()
        paths.append(os.path.join(self.out_dir, "scenarios.csv"))
        paths.append(self.gen_scenario_names())
        paths.append(self.gen_risk_report_profile())
        paths.append(self.gen_temperature_logs())
        paths.append(self.gen_corrective_actions())
        return paths


def derive_seed(customer_name: str) -> int:
    h = hashlib.sha256(customer_name.strip().lower().encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--customer-name", required=True, help='e.g. "Big Sky Grill"')
    p.add_argument("--out-dir", required=True, help="directory to write CSVs into")
    p.add_argument("--num-stores", type=int, default=20)
    p.add_argument("--critical-stores", type=int, default=1,
                   help="number of stores biased toward bad scores, for demo narrative")
    p.add_argument("--as-of", default=None, help="YYYY-MM-DD anchor date; default: today")
    p.add_argument("--seed", type=int, default=None,
                   help="override the deterministic per-customer-name seed")
    return p.parse_args()


def main():
    args = parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    seed = args.seed if args.seed is not None else derive_seed(args.customer_name)
    rng = random.Random(seed)
    gen = DemoDataGenerator(
        customer_name=args.customer_name,
        out_dir=args.out_dir,
        num_stores=args.num_stores,
        critical_stores=args.critical_stores,
        as_of=as_of,
        rng=rng,
    )
    paths = gen.generate_all()
    print(f"Generated {len(paths)} CSVs for '{args.customer_name}' (seed={seed}, as_of={as_of}) in {args.out_dir}:")
    for p in paths:
        print(" -", p)


if __name__ == "__main__":
    main()
