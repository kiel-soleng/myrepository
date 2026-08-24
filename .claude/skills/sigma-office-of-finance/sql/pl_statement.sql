-- Synthetic P&L statement, monthly, trailing 12 months. Extends the same
-- seed constants as budget_actuals.sql (Product Revenue / Sales & Marketing
-- / R&D / G&A / Customer Success) so this page's totals reconcile with
-- Page 1's department rollup by construction, rather than being a
-- disconnected fabrication. Swap the `calc` CTE's seed constants per
-- prospect.
--
-- Sigma tables have no native mid-table subtotal-row support, so the
-- subtotal rows (Gross Profit, Operating Income, Net Income) are computed
-- here in SQL and emitted as ordinary rows with an explicit "Line Order" —
-- the workbook table/pivot sorts by that column rather than relying on
-- row-insertion order (see reference/specification/tables.md, pivot
-- rowsBy[].sort). No trailing semicolon (see reference/specification/
-- sources.md -> "sql — custom SQL query").
WITH months AS (
    SELECT DATEADD('month', SEQ4(), DATE '2025-09-01') AS period_month, SEQ4() AS month_index
    FROM TABLE(GENERATOR(ROWCOUNT => 12))
),
calc AS (
    SELECT
        period_month, month_index,
        ROUND(2450000 * POWER(1.015, month_index)
              * (1 + 0.07 * SIN(2 * PI() * (month_index / 12.0) + 0.3))
              * CASE WHEN MONTH(period_month) = 1 THEN 0.90 ELSE 1.0 END, 0) AS revenue,
        ROUND(420000 * POWER(1.03, month_index)
              * CASE WHEN MONTH(period_month) IN (11, 12) THEN 1.22 ELSE 1.0 END, 0) AS sales_marketing,
        ROUND(610000 * POWER(0.99, month_index), 0) AS rd,
        ROUND(265000 * POWER(1.00, month_index), 0) AS ga,
        ROUND(180000 * POWER(1.02, month_index), 0) AS customer_success
    FROM months
),
derived AS (
    SELECT *,
        ROUND(revenue * 0.32, 0) AS cogs,
        ROUND(revenue - revenue * 0.32, 0) AS gross_profit,
        ROUND(revenue - revenue * 0.32 - sales_marketing - rd - ga - customer_success, 0) AS operating_income
    FROM calc
),
final AS (
    SELECT *,
        ROUND(operating_income * 0.21, 0) AS income_tax,
        ROUND(operating_income * 0.79, 0) AS net_income
    FROM derived
),
lines AS (
    SELECT period_month, 1  AS line_order, 'Revenue'  AS section, 'Revenue'             AS line_item, revenue          AS amount FROM final
    UNION ALL SELECT period_month, 2,  'COGS',     'Cost of Goods Sold', cogs             FROM final
    UNION ALL SELECT period_month, 3,  'Subtotal', 'Gross Profit',       gross_profit     FROM final
    UNION ALL SELECT period_month, 4,  'Opex',     'Sales & Marketing',  sales_marketing  FROM final
    UNION ALL SELECT period_month, 5,  'Opex',     'R&D',                rd               FROM final
    UNION ALL SELECT period_month, 6,  'Opex',     'G&A',                ga               FROM final
    UNION ALL SELECT period_month, 7,  'Opex',     'Customer Success',   customer_success FROM final
    UNION ALL SELECT period_month, 8,  'Subtotal', 'Operating Income',   operating_income FROM final
    UNION ALL SELECT period_month, 9,  'Tax',      'Income Tax',         income_tax       FROM final
    UNION ALL SELECT period_month, 10, 'Subtotal', 'Net Income',         net_income        FROM final
)
-- Line Item is prefixed with its zero-padded Line Order (e.g. "03. Gross
-- Profit") so the pivot's default row sort (which a pivot rowsBy[].sort
-- pointing at a SEPARATE dimension column failed to do — see
-- reference/history.md 2026-08-24) lands in correct accounting order
-- without any extra pivot config.
SELECT
    period_month                                   AS "Period Month",
    line_order                                      AS "Line Order",
    section                                         AS "Section",
    LPAD(line_order, 2, '0') || '. ' || line_item   AS "Line Item",
    amount                                           AS "Amount"
FROM lines
ORDER BY period_month, line_order
