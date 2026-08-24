-- Synthetic General Ledger — journal-entry-line grain, trailing ~4 months.
-- Distinct from close_exceptions.sql's reconciliation-exception list: this
-- is transaction detail (one row per debit/credit line), not a punch-list.
-- Balanced by construction: every entry_id contributes exactly one debit
-- row and one credit row of equal amount, so Sum(Debit) = Sum(Credit)
-- across the whole table — a real trial-balance KPI is meaningful here.
-- Deterministic (SIN-based amounts, not RANDOM()) so re-running the query
-- reproduces the same demo data, matching the other sql/*.sql files'
-- convention. No trailing semicolon (see reference/specification/
-- sources.md -> "sql — custom SQL query").
WITH seq AS (
    SELECT SEQ4() AS i FROM TABLE(GENERATOR(ROWCOUNT => 150))
),
dept AS (
    SELECT * FROM (VALUES
        (0, 'Sales & Marketing'),
        (1, 'R&D'),
        (2, 'G&A'),
        (3, 'Customer Success')
    ) AS d(idx, department)
),
base AS (
    SELECT
        seq.i AS i,
        DATEADD('day', MOD(seq.i * 7, 111), DATE '2026-05-01') AS entry_date,
        MOD(seq.i, 5) AS pattern,
        d.department AS department,
        ROUND(3500 + 2500 * ABS(SIN(seq.i * 0.37)), 0) AS base_amount
    FROM seq
    JOIN dept d ON d.idx = MOD(seq.i, 4)
),
je AS (
    -- pattern 0: revenue recognition -- Dr Accounts Receivable / Cr Product Revenue
    SELECT i, entry_date, 'Revenue' AS category, ROUND(base_amount * 4, 0) AS amt,
           'Accounts Receivable' AS debit_account, 'Product Revenue' AS credit_account,
           'Invoice — subscription revenue' AS description
    FROM base WHERE pattern = 0
    UNION ALL
    -- pattern 1: cash collection -- Dr Cash / Cr Accounts Receivable
    SELECT i, entry_date, 'Revenue', ROUND(base_amount * 3.6, 0),
           'Cash', 'Accounts Receivable', 'Customer payment received'
    FROM base WHERE pattern = 1
    UNION ALL
    -- pattern 2: payroll -- Dr Compensation Expense (dept) / Cr Cash
    SELECT i, entry_date, department, ROUND(base_amount * 6, 0),
           department || ' — Compensation Expense', 'Cash', 'Payroll run'
    FROM base WHERE pattern = 2
    UNION ALL
    -- pattern 3: vendor expense -- Dr Opex (dept) / Cr Accounts Payable
    SELECT i, entry_date, department, base_amount,
           department || ' — Vendor Expense', 'Accounts Payable', 'Vendor invoice'
    FROM base WHERE pattern = 3
    UNION ALL
    -- pattern 4: AP payment -- Dr Accounts Payable / Cr Cash
    SELECT i, entry_date, department, ROUND(base_amount * 0.9, 0),
           'Accounts Payable', 'Cash', 'Vendor payment'
    FROM base WHERE pattern = 4
),
je_id AS (
    SELECT 'JE-' || LPAD(i + 1, 5, '0') AS entry_id, entry_date, category, amt,
           debit_account, credit_account, description
    FROM je
)
SELECT
    entry_id       AS "Entry ID",
    entry_date     AS "Entry Date",
    category       AS "Category",
    debit_account  AS "Account",
    description    AS "Description",
    amt            AS "Debit",
    0               AS "Credit"
FROM je_id
UNION ALL
SELECT
    entry_id, entry_date, category, credit_account, description, 0, amt
FROM je_id
ORDER BY "Entry Date", "Entry ID"
