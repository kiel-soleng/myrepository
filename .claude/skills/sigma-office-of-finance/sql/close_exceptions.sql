-- Synthetic financial-close checklist + reconciliation exceptions for the
-- most recent period. Two result shapes in one file (comment-delimited) —
-- split into two data model elements when wiring up the workbook.

-- === Close calendar / checklist ===
WITH tasks AS (
    SELECT 'Bank Reconciliation'        AS task, 'Treasury'    AS owner, 1 AS days_after_period_end, 'Done'        AS status
    UNION ALL SELECT 'AP Sub-ledger Close',       'AP Team',      2, 'Done'
    UNION ALL SELECT 'AR Sub-ledger Close',       'AR Team',      2, 'In Progress'
    UNION ALL SELECT 'Fixed Asset Roll-forward',  'Controller',   3, 'In Progress'
    UNION ALL SELECT 'Intercompany Elimination',  'Controller',   4, 'Not Started'
    UNION ALL SELECT 'Revenue Recognition Review', 'Revenue Acct', 4, 'Blocked'
    UNION ALL SELECT 'Payroll Accrual',           'HR Finance',   2, 'Done'
    UNION ALL SELECT 'Management Review & Sign-off', 'CFO',       6, 'Not Started'
)
SELECT
    task, owner,
    DATEADD('day', days_after_period_end, DATE_TRUNC('month', CURRENT_DATE)) AS due_date,
    status,
    DATEDIFF('day', CURRENT_DATE, DATEADD('day', days_after_period_end, DATE_TRUNC('month', CURRENT_DATE))) AS days_until_due
FROM tasks
ORDER BY due_date;

-- === Reconciliation exceptions ===
WITH accounts AS (
    SELECT 'Accounts Receivable' AS account, 'Timing Difference' AS exception_type, 42000 AS amount, 9 AS days_open
    UNION ALL SELECT 'Prepaid Expenses',      'Unmatched Entry',    8500,  3
    UNION ALL SELECT 'Accrued Liabilities',   'Missing Support',   15200, 14
    UNION ALL SELECT 'Fixed Assets',          'Depreciation Error', 3100,  2
    UNION ALL SELECT 'Intercompany AR',       'Currency Rounding',   950,  6
)
SELECT account, exception_type, amount, days_open,
       CASE WHEN days_open > 5 THEN 'Aged' ELSE 'Current' END AS age_bucket
FROM accounts
ORDER BY days_open DESC
