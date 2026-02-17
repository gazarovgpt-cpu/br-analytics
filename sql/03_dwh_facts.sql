-- Белая Радуга: DWH Fact tables

-- ============================================================
-- Факт: Транзакции (нормализованная версия raw.mis_transactions)
-- ============================================================
CREATE TABLE IF NOT EXISTS dwh.fact_transactions (
    transaction_id      BIGSERIAL PRIMARY KEY,
    transaction_date    DATE NOT NULL,
    branch_id           INT REFERENCES dwh.dim_branch(branch_id),
    patient_hash        TEXT,               -- SHA256 от patient_name
    patient_age         INT,
    is_child            BOOLEAN,
    payment_type_id     INT REFERENCES dwh.dim_payment_type(payment_type_id),
    operation_type      TEXT NOT NULL,       -- "Оплата" / "Возврат оплаты"
    invoice_branch_id   INT REFERENCES dwh.dim_branch(branch_id),
    invoice_amount      NUMERIC(15,2),
    invoice_debt        NUMERIC(15,2),
    service_id          INT REFERENCES dwh.dim_service(service_id),
    service_name        TEXT,               -- сырое название для аналитики
    visit_date          DATE,
    doctor_id           INT REFERENCES dwh.dim_doctor(doctor_id),
    is_primary_visit    BOOLEAN,            -- TRUE if "Первичный"
    transaction_amount  NUMERIC(15,2) NOT NULL,

    CONSTRAINT chk_operation_type CHECK (operation_type IN ('Оплата', 'Возврат оплаты'))
);

CREATE INDEX IF NOT EXISTS idx_fact_tx_date ON dwh.fact_transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_fact_tx_branch ON dwh.fact_transactions(branch_id);
CREATE INDEX IF NOT EXISTS idx_fact_tx_doctor ON dwh.fact_transactions(doctor_id);
CREATE INDEX IF NOT EXISTS idx_fact_tx_patient ON dwh.fact_transactions(patient_hash);

-- ============================================================
-- Факт: Cash Flow записи (из проводок 1С)
-- ============================================================
CREATE TABLE IF NOT EXISTS dwh.fact_cf_entries (
    cf_entry_id         BIGSERIAL PRIMARY KEY,
    entry_date          DATE NOT NULL,
    legal_entity_id     INT REFERENCES dwh.dim_legal_entity(legal_entity_id),
    branch_id           INT REFERENCES dwh.dim_branch(branch_id),
    expense_type_id     INT REFERENCES dwh.dim_expense_type(expense_type_id),
    direction           TEXT NOT NULL,       -- "Поступление" / "Расход"
    amount              NUMERIC(15,2) NOT NULL,
    counterparty        TEXT,
    description         TEXT
);

CREATE INDEX IF NOT EXISTS idx_fact_cf_date ON dwh.fact_cf_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_fact_cf_branch ON dwh.fact_cf_entries(branch_id);

-- ============================================================
-- Факт: Сводный CF помесячно (из CF_СВОД)
-- ============================================================
CREATE TABLE IF NOT EXISTS dwh.fact_cf_monthly (
    cf_monthly_id       BIGSERIAL PRIMARY KEY,
    year_month          DATE NOT NULL,      -- первый день месяца
    legal_entity_id     INT REFERENCES dwh.dim_legal_entity(legal_entity_id),
    branch_id           INT,                -- nullable, не всегда есть разбивка по филиалам
    line_item           TEXT NOT NULL,       -- статья ДДС
    expense_type_id     INT REFERENCES dwh.dim_expense_type(expense_type_id),
    amount              NUMERIC(15,2) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fact_cf_m_month ON dwh.fact_cf_monthly(year_month);

-- ============================================================
-- Факт: Себестоимость по процедурам (unit economics)
-- ============================================================
CREATE TABLE IF NOT EXISTS dwh.fact_cost_structure (
    cost_id             SERIAL PRIMARY KEY,
    service_id          INT REFERENCES dwh.dim_service(service_id),
    service_code        TEXT,
    service_name        TEXT,
    price               NUMERIC(10,2),
    material_cost       NUMERIC(10,2),
    material_pct        NUMERIC(5,4),
    doctor_pay          NUMERIC(10,2),
    assistant_pay       NUMERIC(10,2),
    taxes               NUMERIC(10,2),
    total_cost          NUMERIC(10,2),
    margin_rub          NUMERIC(10,2),
    margin_pct          NUMERIC(5,4),
    effective_date      DATE DEFAULT CURRENT_DATE
);

-- ============================================================
-- Факт: Лиды помесячно
-- ============================================================
CREATE TABLE IF NOT EXISTS dwh.fact_leads (
    lead_id             SERIAL PRIMARY KEY,
    year_month          DATE NOT NULL,
    lead_type           TEXT NOT NULL,       -- "Первичные" / "Вторичные"
    count               INT NOT NULL
);

-- ============================================================
-- Факт: Бухгалтерская отчётность (ОФР ключевые строки)
-- ============================================================
CREATE TABLE IF NOT EXISTS dwh.fact_financial_statements (
    fs_id               SERIAL PRIMARY KEY,
    legal_entity_id     INT REFERENCES dwh.dim_legal_entity(legal_entity_id),
    period_end          DATE NOT NULL,
    line_code           TEXT NOT NULL,       -- "2110", "2120", "2400" и т.д.
    line_name           TEXT NOT NULL,
    amount_ths_rub      NUMERIC(15,2),      -- тыс. руб.
    amount_prev_ths_rub NUMERIC(15,2)
);
