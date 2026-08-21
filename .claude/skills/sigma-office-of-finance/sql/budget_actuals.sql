-- Synthetic budget-vs-actual by department, trailing 12 months.
-- Swap the `dept` seed block per prospect (department names + base budget +
-- variance-tendency knobs) — everything downstream (months, actuals,
-- variance) is derived, mirroring the constants-at-top pattern in
-- sigma-company-dashboard-v2/sql/nim_bridge.sql. Output columns are
-- explicitly quote-aliased to display names, matching the
-- `[Custom SQL/<Name>]` passthrough convention used when this is wired up
-- as a workbook table element via source.kind: "sql".
WITH dept AS (
    SELECT 'Sales & Marketing'   AS department, 'Expense' AS account_type, 420000 AS monthly_budget, 0.03 AS drift, 0.06 AS noise, 0.0 AS phase
    UNION ALL SELECT 'R&D',                       'Expense', 610000, -0.01, 0.05, 1.4
    UNION ALL SELECT 'G&A',                        'Expense', 265000,  0.00, 0.04, 0.6
    UNION ALL SELECT 'Customer Success',            'Expense', 180000,  0.02, 0.05, 2.1
    UNION ALL SELECT 'Product Revenue',             'Revenue', 2450000, 0.015, 0.07, 0.3
),
months AS (
    SELECT DATEADD('month', SEQ4(), DATE '2025-09-01') AS period_month, SEQ4() AS month_index
    FROM TABLE(GENERATOR(ROWCOUNT => 12))
)
SELECT
    m.period_month                                                                        AS "Period Month",
    d.department                                                                          AS "Department",
    d.account_type                                                                        AS "Account Type",
    ROUND(d.monthly_budget * POWER(1 + d.drift, m.month_index), 0)                        AS "Budget Amount",
    ROUND(d.monthly_budget * POWER(1 + d.drift, m.month_index)
          * (1 + d.noise * SIN(2 * PI() * (m.month_index / 12.0) + d.phase))
          * CASE WHEN d.department = 'Sales & Marketing' AND MONTH(m.period_month) IN (11, 12) THEN 1.22
                 WHEN d.department = 'Product Revenue' AND MONTH(m.period_month) IN (1) THEN 0.90
                 ELSE 1.0 END, 0)                                                          AS "Actual Amount"
FROM dept d
CROSS JOIN months m
ORDER BY m.period_month, d.department;
