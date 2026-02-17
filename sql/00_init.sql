-- Белая Радуга: Analytics DWH
-- Инициализация схем

CREATE SCHEMA IF NOT EXISTS raw;      -- staging: сырые данные из источников
CREATE SCHEMA IF NOT EXISTS dwh;      -- star schema: измерения и факты
CREATE SCHEMA IF NOT EXISTS marts;    -- витрины: агрегаты для дашбордов

COMMENT ON SCHEMA raw   IS 'Staging area: raw data from MIS, 1C, Excel';
COMMENT ON SCHEMA dwh   IS 'Star schema: dimensions and facts';
COMMENT ON SCHEMA marts  IS 'Materialized views for dashboards and BI';
