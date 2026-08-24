-- Baseline run-rate for the Page 3 rolling forecast (input-table-app
-- pattern). This feeds the LINKED input table, not the input table
-- itself — the editable "Forecast Entry" column is created by the
-- workbook spec's input table, not by SQL. Keep category labels identical
-- to budget_actuals.sql's `department` values so Page 1 and Page 3 stay
-- comparable, per reference/kpis.md's cross-page reconciliation note.
WITH trailing AS (
    SELECT department, AVG(actual_amount) AS trailing_avg
    FROM (
        -- in production, point this at the same source as budget_actuals.sql
        -- filtered to the trailing 3 closed months; inlined here as a stand-in
        SELECT 'Sales & Marketing' AS department, 480000 AS actual_amount UNION ALL
        SELECT 'Sales & Marketing', 465000 UNION ALL
        SELECT 'Sales & Marketing', 471000 UNION ALL
        SELECT 'R&D',               605000 UNION ALL
        SELECT 'R&D',               598000 UNION ALL
        SELECT 'R&D',               611000 UNION ALL
        SELECT 'G&A',               263000 UNION ALL
        SELECT 'G&A',               266000 UNION ALL
        SELECT 'G&A',               264000 UNION ALL
        SELECT 'Customer Success',  184000 UNION ALL
        SELECT 'Customer Success',  179000 UNION ALL
        SELECT 'Customer Success',  183000 UNION ALL
        SELECT 'Product Revenue',   2510000 UNION ALL
        SELECT 'Product Revenue',   2489000 UNION ALL
        SELECT 'Product Revenue',   2532000
    )
    GROUP BY department
),
future_months AS (
    SELECT DATEADD('month', SEQ4() + 1, DATE_TRUNC('month', CURRENT_DATE)) AS period_month, SEQ4() AS month_index
    FROM TABLE(GENERATOR(ROWCOUNT => 6))
)
SELECT
    fm.period_month                       AS "Period Month",
    t.department                          AS "Department",
    ROUND(t.trailing_avg, 0)               AS "Base Case"   -- seeds the hidden Base Case column; Forecast Entry stays user-editable/blank
FROM trailing t
CROSS JOIN future_months fm
ORDER BY fm.period_month, t.department
