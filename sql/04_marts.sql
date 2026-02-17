-- Белая Радуга: Marts (витрины для дашбордов)

-- ============================================================
-- Витрина: P&L помесячно по филиалам
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS marts.monthly_pnl AS
WITH
-- Выручка accrual (из МИС транзакций)
revenue_accrual AS (
    SELECT
        DATE_TRUNC('month', transaction_date)::DATE AS year_month,
        branch_id,
        SUM(CASE WHEN operation_type = 'Оплата' THEN transaction_amount ELSE 0 END) AS gross_revenue,
        SUM(CASE WHEN operation_type = 'Возврат оплаты' THEN ABS(transaction_amount) ELSE 0 END) AS refunds,
        SUM(transaction_amount) AS net_revenue,
        COUNT(DISTINCT patient_hash) AS unique_patients,
        COUNT(*) FILTER (WHERE operation_type = 'Оплата') AS payment_count,
        COUNT(*) FILTER (WHERE is_primary_visit = TRUE AND operation_type = 'Оплата') AS primary_visits,
        AVG(CASE WHEN operation_type = 'Оплата' THEN transaction_amount END) AS avg_ticket
    FROM dwh.fact_transactions
    GROUP BY 1, 2
),
-- Cash flow по статьям (из CF помесячных данных)
cf_summary AS (
    SELECT
        year_month,
        branch_id,
        SUM(amount) FILTER (WHERE line_item ILIKE '%приход%операц%' OR line_item ILIKE '%выручк%') AS cash_revenue,
        SUM(ABS(amount)) FILTER (WHERE line_item ILIKE '%материал%') AS materials,
        SUM(ABS(amount)) FILTER (WHERE line_item ILIKE '%лаборатор%') AS lab,
        SUM(ABS(amount)) FILTER (WHERE line_item ILIKE '%зарплат%доктор%' OR line_item ILIKE '%ФОТ%врач%') AS payroll_doctors,
        SUM(ABS(amount)) FILTER (WHERE line_item ILIKE '%зарплат%ассист%') AS payroll_assistants,
        SUM(ABS(amount)) FILTER (WHERE line_item ILIKE '%аренд%') AS rent,
        SUM(ABS(amount)) FILTER (WHERE line_item ILIKE '%маркетинг%' OR line_item ILIKE '%реклам%') AS marketing,
        SUM(ABS(amount)) FILTER (WHERE line_item ILIKE '%IT%' OR line_item ILIKE '%клиник айкью%') AS it_costs
    FROM dwh.fact_cf_monthly
    GROUP BY 1, 2
)
SELECT
    COALESCE(r.year_month, c.year_month) AS year_month,
    COALESCE(r.branch_id, c.branch_id) AS branch_id,
    b.display_name AS branch_name,
    -- Revenue
    r.net_revenue AS revenue_accrual,
    c.cash_revenue AS revenue_cash,
    r.gross_revenue,
    r.refunds,
    r.avg_ticket,
    r.unique_patients,
    r.payment_count,
    r.primary_visits,
    -- Cost of goods
    c.materials,
    c.lab,
    COALESCE(r.net_revenue, 0) - COALESCE(c.materials, 0) - COALESCE(c.lab, 0) AS gross_margin,
    -- Payroll
    c.payroll_doctors,
    c.payroll_assistants,
    COALESCE(c.payroll_doctors, 0) + COALESCE(c.payroll_assistants, 0) AS total_payroll_direct,
    -- OPEX
    c.rent,
    c.marketing,
    c.it_costs,
    -- EBITDA
    COALESCE(r.net_revenue, 0)
        - COALESCE(c.materials, 0)
        - COALESCE(c.lab, 0)
        - COALESCE(c.payroll_doctors, 0)
        - COALESCE(c.payroll_assistants, 0)
        - COALESCE(c.rent, 0)
        - COALESCE(c.marketing, 0)
        - COALESCE(c.it_costs, 0) AS ebitda
FROM revenue_accrual r
FULL OUTER JOIN cf_summary c USING (year_month, branch_id)
LEFT JOIN dwh.dim_branch b ON COALESCE(r.branch_id, c.branch_id) = b.branch_id
ORDER BY year_month, branch_id;

-- ============================================================
-- Витрина: KPI врачей помесячно
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS marts.doctor_kpi AS
SELECT
    DATE_TRUNC('month', t.transaction_date)::DATE AS year_month,
    t.doctor_id,
    d.full_name AS doctor_name,
    d.specialization,
    t.branch_id,
    b.display_name AS branch_name,
    SUM(t.transaction_amount) FILTER (WHERE t.operation_type = 'Оплата') AS revenue,
    COUNT(*) FILTER (WHERE t.operation_type = 'Оплата') AS visit_count,
    COUNT(DISTINCT t.patient_hash) AS unique_patients,
    COUNT(*) FILTER (WHERE t.is_primary_visit = TRUE AND t.operation_type = 'Оплата') AS primary_visits,
    AVG(t.transaction_amount) FILTER (WHERE t.operation_type = 'Оплата') AS avg_ticket,
    SUM(t.transaction_amount) FILTER (WHERE t.operation_type = 'Оплата')
        / GREATEST(COUNT(DISTINCT t.transaction_date) FILTER (WHERE t.operation_type = 'Оплата'), 1)
        AS revenue_per_workday
FROM dwh.fact_transactions t
LEFT JOIN dwh.dim_doctor d ON t.doctor_id = d.doctor_id
LEFT JOIN dwh.dim_branch b ON t.branch_id = b.branch_id
WHERE t.doctor_id IS NOT NULL
GROUP BY 1, 2, 3, 4, 5, 6
ORDER BY year_month, revenue DESC;

-- ============================================================
-- Витрина: Сравнение филиалов
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS marts.branch_comparison AS
SELECT
    DATE_TRUNC('month', t.transaction_date)::DATE AS year_month,
    t.branch_id,
    b.display_name AS branch_name,
    SUM(t.transaction_amount) FILTER (WHERE t.operation_type = 'Оплата') AS revenue,
    SUM(t.transaction_amount) AS net_revenue,
    COUNT(*) FILTER (WHERE t.operation_type = 'Оплата') AS payments,
    COUNT(DISTINCT t.patient_hash) AS unique_patients,
    COUNT(*) FILTER (WHERE t.is_primary_visit AND t.operation_type = 'Оплата') AS primary_visits,
    AVG(t.transaction_amount) FILTER (WHERE t.operation_type = 'Оплата') AS avg_ticket,
    SUM(t.transaction_amount) FILTER (WHERE t.is_child = TRUE AND t.operation_type = 'Оплата') AS children_revenue,
    SUM(t.transaction_amount) FILTER (WHERE t.is_child = FALSE AND t.operation_type = 'Оплата') AS adult_revenue
FROM dwh.fact_transactions t
LEFT JOIN dwh.dim_branch b ON t.branch_id = b.branch_id
GROUP BY 1, 2, 3
ORDER BY year_month, revenue DESC;

-- ============================================================
-- Витрина: Экономика услуг
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS marts.service_economics AS
SELECT
    t.service_name,
    t.branch_id,
    b.display_name AS branch_name,
    COUNT(*) FILTER (WHERE t.operation_type = 'Оплата') AS service_count,
    SUM(t.transaction_amount) FILTER (WHERE t.operation_type = 'Оплата') AS total_revenue,
    AVG(t.transaction_amount) FILTER (WHERE t.operation_type = 'Оплата') AS avg_price,
    cs.material_cost,
    cs.doctor_pay,
    cs.margin_pct
FROM dwh.fact_transactions t
LEFT JOIN dwh.dim_branch b ON t.branch_id = b.branch_id
LEFT JOIN dwh.fact_cost_structure cs ON t.service_name = cs.service_name
WHERE t.service_name IS NOT NULL
GROUP BY 1, 2, 3, cs.material_cost, cs.doctor_pay, cs.margin_pct
HAVING COUNT(*) FILTER (WHERE t.operation_type = 'Оплата') >= 5
ORDER BY total_revenue DESC;

-- ============================================================
-- Витрина: Алерты оптимизации
-- ============================================================
CREATE TABLE IF NOT EXISTS marts.alerts (
    alert_id        SERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    year_month      DATE,
    branch_id       INT,
    branch_name     TEXT,
    doctor_id       INT,
    doctor_name     TEXT,
    alert_type      TEXT NOT NULL,       -- "margin_drop", "material_spike", "discount_spike", etc.
    severity        TEXT NOT NULL,       -- "critical", "warning", "info"
    metric_name     TEXT,
    metric_value    NUMERIC(15,4),
    threshold_value NUMERIC(15,4),
    description     TEXT NOT NULL,
    recommendation  TEXT
);
