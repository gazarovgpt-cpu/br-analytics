-- Белая Радуга: DWH Dimensions (star schema)

-- ============================================================
-- Календарь
-- ============================================================
CREATE TABLE IF NOT EXISTS dwh.dim_date (
    date_id         DATE PRIMARY KEY,
    day_of_month    INT,
    day_of_week     INT,            -- 1=Пн, 7=Вс
    day_name        TEXT,           -- "Понедельник" и т.д.
    week_of_year    INT,
    month_num       INT,
    month_name      TEXT,           -- "Январь" и т.д.
    quarter         INT,
    year            INT,
    is_workday      BOOLEAN,
    year_month      TEXT            -- "2025-01" для группировки
);

-- Заполняем календарь 2022-2027
INSERT INTO dwh.dim_date
SELECT
    d::DATE AS date_id,
    EXTRACT(DAY FROM d)::INT,
    EXTRACT(ISODOW FROM d)::INT,
    TO_CHAR(d, 'TMDay'),
    EXTRACT(WEEK FROM d)::INT,
    EXTRACT(MONTH FROM d)::INT,
    TO_CHAR(d, 'TMMonth'),
    EXTRACT(QUARTER FROM d)::INT,
    EXTRACT(YEAR FROM d)::INT,
    EXTRACT(ISODOW FROM d) <= 5,
    TO_CHAR(d, 'YYYY-MM')
FROM generate_series('2022-01-01'::DATE, '2027-12-31'::DATE, '1 day') AS d
ON CONFLICT (date_id) DO NOTHING;

-- ============================================================
-- Юридические лица
-- ============================================================
CREATE TABLE IF NOT EXISTS dwh.dim_legal_entity (
    legal_entity_id SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    short_name      TEXT NOT NULL,   -- "БР", "БР-1", "БРЦ", "ИП"
    inn             TEXT,
    entity_type     TEXT,            -- "ООО" / "ИП"
    address         TEXT,
    is_active       BOOLEAN DEFAULT TRUE
);

INSERT INTO dwh.dim_legal_entity (name, short_name, inn, entity_type, address) VALUES
    ('ООО "БЕЛАЯ РАДУГА"',         'БР',   '9705103146', 'ООО', '115172, Москва, Котельническая наб, 25, стр.1'),
    ('ООО "Белая Радуга-1"',       'БР-1', '9701131216', 'ООО', '105066, Москва, Нижняя Красносельская ул, 35, стр.50'),
    ('ООО "БЕЛАЯ РАДУГА - ЦЕНТР"', 'БРЦ',  '9704221570', 'ООО', '119048, Москва, ул Усачёва, 11'),
    ('ИП Артеменко',               'ИП',   NULL,         'ИП',  NULL)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Филиалы (клиники)
-- ============================================================
CREATE TABLE IF NOT EXISTS dwh.dim_branch (
    branch_id       SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    code            TEXT NOT NULL UNIQUE,    -- "taganskaya", "baumanskaya" и т.д.
    display_name    TEXT NOT NULL,           -- "Таганская", "Бауманская" и т.д.
    legal_entity_id INT REFERENCES dwh.dim_legal_entity(legal_entity_id),
    mis_name        TEXT,                    -- как в МИС: "(Таганская)"
    cf_name         TEXT,                    -- как в CF из 1С: "Таганка"
    address         TEXT,
    is_active       BOOLEAN DEFAULT TRUE
);

INSERT INTO dwh.dim_branch (name, code, display_name, legal_entity_id, mis_name, cf_name) VALUES
    ('Таганская',    'taganskaya',   'Таганская',    1, '(Таганская)',   'Таганка'),
    ('Бауманская',   'baumanskaya',  'Бауманская',   1, '(Бауманская)',  'Бауманская'),
    ('Динамо',       'dinamo',       'Динамо',       1, '(Динамо)',      'Динамо'),
    ('Зиларт',       'zilart',       'Зиларт',       1, '(Зиларт)',      'Зиларт'),
    ('Рублевка',     'rublevka',     'Рублевка',     1, '(Рублевка)',    'Рублевка'),
    ('Хамовники',    'khamovniki',   'Хамовники',    3, '(Хамовники)',   'Хамовники')
ON CONFLICT DO NOTHING;

COMMENT ON COLUMN dwh.dim_branch.legal_entity_id IS 'Primary legal entity. Note: БР and БР-1 both serve same clinics, БРЦ = Хамовники';

-- ============================================================
-- Врачи (заполняется из ETL)
-- ============================================================
CREATE TABLE IF NOT EXISTS dwh.dim_doctor (
    doctor_id       SERIAL PRIMARY KEY,
    full_name       TEXT NOT NULL,
    name_hash       TEXT,                   -- для обезличивания
    specialization  TEXT,
    primary_branch_id INT REFERENCES dwh.dim_branch(branch_id),
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dim_doctor_name ON dwh.dim_doctor(full_name);

-- ============================================================
-- Справочник услуг (заполняется из ETL)
-- ============================================================
CREATE TABLE IF NOT EXISTS dwh.dim_service (
    service_id      SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    code            TEXT,
    category        TEXT,           -- "Терапия", "Хирургия", "Ортопедия", "Ортодонтия", "Гигиена", "Седация", "Прочее"
    base_price      NUMERIC(10,2)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dim_service_name ON dwh.dim_service(name);

-- ============================================================
-- Типы оплат
-- ============================================================
CREATE TABLE IF NOT EXISTS dwh.dim_payment_type (
    payment_type_id SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    is_cash         BOOLEAN DEFAULT FALSE
);

INSERT INTO dwh.dim_payment_type (name, is_cash) VALUES
    ('Карта', FALSE),
    ('Наличные б/ч', TRUE),
    ('ИП Артеменко', FALSE),
    ('Бонусы (карта АЕ)', FALSE),
    ('Прочие', FALSE)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Статьи расходов (из CF)
-- ============================================================
CREATE TABLE IF NOT EXISTS dwh.dim_expense_type (
    expense_type_id SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    category        TEXT,           -- "Выручка", "Себестоимость", "Прямые", "ФОТ", "OPEX"
    parent_category TEXT,
    sort_order      INT
);

INSERT INTO dwh.dim_expense_type (name, category, parent_category, sort_order) VALUES
    -- Выручка
    ('Выручка наличными',                           'Выручка',       'Доходы', 10),
    ('Выручка на расчетный счет (в т.ч. Карты)',    'Выручка',       'Доходы', 11),
    ('Выручка безналичными',                        'Выручка',       'Доходы', 12),
    ('Кредитные карты ИП',                          'Выручка',       'Доходы', 13),
    ('Бонусы (карта АЕ)',                           'Выручка',       'Доходы', 14),
    ('Прочие поступления',                          'Выручка',       'Доходы', 15),
    -- Прямые затраты
    ('Заработная плата докторов (в т.ч. взносы)',    'ФОТ врачей',    'Себестоимость', 20),
    ('Заработная плата ассистентов (в т.ч. взносы)', 'ФОТ ассистентов','Себестоимость', 21),
    ('Расходные материалы',                         'Материалы',      'Себестоимость', 30),
    ('Лаборатория',                                 'Лаборатория',    'Себестоимость', 31),
    -- Операционные расходы
    ('Аренда помещений клиник и парковки',           'Аренда',         'OPEX', 40),
    ('Аренда офиса',                                'Аренда',         'OPEX', 41),
    ('Маркетинг',                                   'Маркетинг',      'OPEX', 50),
    ('IT',                                          'IT',             'OPEX', 51),
    ('Клининг',                                     'Клининг',        'OPEX', 52),
    ('Охрана',                                      'Охрана',         'OPEX', 53),
    ('Канцтовары/хозтовары клиник',                 'Хозрасходы',     'OPEX', 54),
    ('Связь и интернет',                            'Связь',          'OPEX', 55),
    ('Коммунальные услуги',                         'Коммуналка',     'OPEX', 56),
    -- Прочее
    ('Налоги',                                      'Налоги',         'Прочее', 60),
    ('Проценты по кредитам',                        'Финансовые',     'Прочее', 70)
ON CONFLICT DO NOTHING;
