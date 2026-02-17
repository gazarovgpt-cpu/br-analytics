-- Белая Радуга: Roles and Row-Level Security

-- ============================================================
-- Роли
-- ============================================================

DO $$
BEGIN
    -- Owner / CEO: полный доступ
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'role_owner') THEN
        CREATE ROLE role_owner;
    END IF;

    -- CFO / Финансы: полный доступ + экспорт
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'role_cfo') THEN
        CREATE ROLE role_cfo;
    END IF;

    -- Управляющий филиала: только свой филиал
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'role_branch_mgr') THEN
        CREATE ROLE role_branch_mgr;
    END IF;

    -- Аналитик: чтение витрин
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'role_analyst') THEN
        CREATE ROLE role_analyst;
    END IF;
END
$$;

-- Права
GRANT USAGE ON SCHEMA raw, dwh, marts TO role_owner, role_cfo;
GRANT SELECT ON ALL TABLES IN SCHEMA raw TO role_owner, role_cfo;
GRANT SELECT ON ALL TABLES IN SCHEMA dwh TO role_owner, role_cfo;
GRANT SELECT ON ALL TABLES IN SCHEMA marts TO role_owner, role_cfo, role_branch_mgr, role_analyst;

-- Права по умолчанию для новых объектов
ALTER DEFAULT PRIVILEGES IN SCHEMA raw   GRANT SELECT ON TABLES TO role_owner, role_cfo;
ALTER DEFAULT PRIVILEGES IN SCHEMA dwh   GRANT SELECT ON TABLES TO role_owner, role_cfo;
ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO role_owner, role_cfo, role_branch_mgr, role_analyst;

-- ============================================================
-- Row-Level Security для управляющих филиалов
-- ============================================================

-- RLS на mart витринах (branch_comparison, monthly_pnl)
-- Управляющий видит только свой branch_id

-- Пример для future use: создание пользователя-управляющего
-- CREATE USER mgr_taganskaya WITH PASSWORD '...' IN ROLE role_branch_mgr;
-- ALTER USER mgr_taganskaya SET app.branch_id = '1';

-- RLS policy (активируется при необходимости)
-- ALTER TABLE marts.alerts ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY branch_filter ON marts.alerts
--     FOR SELECT TO role_branch_mgr
--     USING (branch_id = CURRENT_SETTING('app.branch_id')::INT);
