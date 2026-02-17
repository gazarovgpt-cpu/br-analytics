-- Белая Радуга: Raw (staging) tables
-- Структура точно соответствует реальным файлам

-- ============================================================
-- 1. Транзакции из МИС (Детализация_транзакций_+_услуги)
--    Источник: 51,751 строк, ClinicIQ
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.mis_transactions (
    id                  BIGSERIAL PRIMARY KEY,
    transaction_date    DATE,
    clinic              TEXT,           -- "(Таганская)", "(Бауманская)" и т.д.
    patient_name        TEXT,           -- будет хэширован при загрузке
    patient_age         INT,
    age_group           TEXT,           -- "Взрослый" / "Ребенок"
    payment_type        TEXT,           -- "Карта", "Наличные б/ч", "ИП Артеменко", "Бонусы"
    operation_type      TEXT,           -- "Оплата", "Возврат оплаты"
    invoice_clinic      TEXT,           -- клиника, где создан счёт
    invoice_amount      NUMERIC(15,2),
    invoice_debt        NUMERIC(15,2),
    invoice_status      TEXT,
    service_items       TEXT,           -- позиции счёта (название услуги)
    visit_dates         TEXT,           -- даты визитов
    visit_reasons       TEXT,           -- причины обращения
    doctor_name         TEXT,
    visit_status        TEXT,           -- "Первичный" / "Повторный"
    transaction_amount  NUMERIC(15,2),
    loaded_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_mis_tx_date ON raw.mis_transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_raw_mis_tx_clinic ON raw.mis_transactions(clinic);

COMMENT ON TABLE raw.mis_transactions IS 'Raw MIS transactions from Детализация_транзакций_+_услуги_2025_01_05.xlsx';

-- ============================================================
-- 2. Cash Flow проводки из 1С (2024_08_БР CF, sheet 2023_офиц)
--    Источник: ~14,000 строк
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.cf_entries (
    id                  BIGSERIAL PRIMARY KEY,
    entry_type          TEXT,           -- "ВЫРУЧКА", "РАСХОД" и т.д.
    direction           TEXT,           -- "Поступление" / "Расход"
    month_num           INT,
    entry_date          DATE,
    document            TEXT,
    description         TEXT,           -- содержание операции
    debit_account       TEXT,           -- Дт
    credit_account      TEXT,           -- Кт
    amount              NUMERIC(15,2),  -- Сумма_УУ
    counterparty        TEXT,           -- контрагент
    branch_uu           TEXT,           -- Подразделение_УУ: "Таганка", "Зиларт" и т.д.
    account_uu          TEXT,           -- Счет_УУ
    expense_category    TEXT,           -- НОВАЯ СТАТЬЯ
    source_file         TEXT,           -- имя файла-источника
    loaded_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_cf_date ON raw.cf_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_raw_cf_branch ON raw.cf_entries(branch_uu);

COMMENT ON TABLE raw.cf_entries IS 'Raw cash flow entries from 1C exports';

-- ============================================================
-- 3. Сводный Cash Flow помесячно (CF_СВОД + CF по клиникам)
--    Источник: CF_СВОД_+_КЛИНИК_АЙ_КЬЮ, 2025_01_БР CF
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.cf_monthly (
    id                  BIGSERIAL PRIMARY KEY,
    year_month          DATE,           -- первый день месяца
    legal_entity        TEXT,           -- "БР", "БР-1", "ИП", "БРЦ"
    branch              TEXT,           -- "ТАГАНКА", "БАУМАНКА" и т.д. (если есть)
    line_item           TEXT,           -- статья ДДС
    amount              NUMERIC(15,2),
    source_file         TEXT,
    loaded_at           TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE raw.cf_monthly IS 'Monthly CF summaries from consolidated reports';

-- ============================================================
-- 4. Средний чек по клиникам (SQL-выгрузка из МИС)
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.avg_ticket (
    id                  SERIAL PRIMARY KEY,
    clinic              TEXT,
    visits              INT,
    total_revenue       NUMERIC(15,2),
    avg_ticket          NUMERIC(10,2),
    source_file         TEXT,
    loaded_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 5. LTV по процедурам
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.ltv_procedures (
    id                  SERIAL PRIMARY KEY,
    procedure_name      TEXT,
    unique_clients      INT,
    total_procedures    INT,
    total_revenue       NUMERIC(15,2),
    avg_procedure_price NUMERIC(10,2),
    min_procedure_price NUMERIC(10,2),
    max_procedure_price NUMERIC(10,2),
    ltv_per_client      NUMERIC(10,2),
    avg_procedures_per_client NUMERIC(5,2),
    loaded_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 6. Топ услуг по клиникам
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.top_services (
    id                  SERIAL PRIMARY KEY,
    clinic              TEXT,
    service_name        TEXT,
    price_with_discount NUMERIC(10,2),
    quantity            INT,
    total_with_discount NUMERIC(15,2),
    loaded_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 7. Себестоимость по процедурам
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.cost_structure (
    id                  SERIAL PRIMARY KEY,
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
    loaded_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 8. Лиды (первичные / вторичные)
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.leads_monthly (
    id                  SERIAL PRIMARY KEY,
    year                INT,
    month               INT,
    lead_type           TEXT,           -- "Первичные" / "Вторичные"
    count               INT,
    loaded_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 9. Источники лидов понедельно
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.lead_sources_weekly (
    id                  SERIAL PRIMARY KEY,
    source              TEXT,
    week_start          DATE,
    week_end            DATE,
    count               INT,
    loaded_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 10. Бухгалтерская отчётность (извлечённые цифры из PDF)
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.financial_statements (
    id                  SERIAL PRIMARY KEY,
    legal_entity        TEXT,           -- "БЕЛАЯ РАДУГА", "Белая Радуга-1", "БЕЛАЯ РАДУГА - ЦЕНТР"
    inn                 TEXT,
    report_type         TEXT,           -- "balance" / "pnl"
    period_start        DATE,
    period_end          DATE,
    line_code           TEXT,           -- код строки (2110, 2120 и т.д.)
    line_name           TEXT,
    amount_current      NUMERIC(15,2), -- тыс. руб.
    amount_previous     NUMERIC(15,2),
    loaded_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 11. YoY анализ (2024 vs 2023)
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.yoy_analysis (
    id                  SERIAL PRIMARY KEY,
    line_item           TEXT,
    amount_2023         NUMERIC(15,2),
    pct_2023            NUMERIC(10,6),
    amount_2024         NUMERIC(15,2),
    pct_2024            NUMERIC(10,6),
    delta_abs           NUMERIC(15,2),
    delta_pct           NUMERIC(10,6),
    delta_share         NUMERIC(10,6),
    loaded_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 12. Расшифровка поставщиков
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.suppliers (
    id                  SERIAL PRIMARY KEY,
    legal_entity        TEXT,
    period              TEXT,
    account             TEXT,           -- счет 60.01, 60.02 и т.д.
    counterparty        TEXT,
    opening_debit       NUMERIC(15,2),
    opening_credit      NUMERIC(15,2),
    turnover_debit      NUMERIC(15,2),
    turnover_credit     NUMERIC(15,2),
    closing_debit       NUMERIC(15,2),
    closing_credit      NUMERIC(15,2),
    loaded_at           TIMESTAMPTZ DEFAULT NOW()
);
