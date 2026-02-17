# Финаналитика: Белая Радуга

Система управленческой аналитики для сети стоматологических клиник "Белая Радуга" (6 филиалов).

## Быстрый старт

### 1. Запуск базы данных

```bash
cp .env.example .env
docker compose up -d
```

PostgreSQL будет доступен на `localhost:5433`, pgAdmin на `http://localhost:8080`.

### 2. Установка зависимостей

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Подготовка данных

Скопируйте исходные файлы в папку `data/`:

```
data/
├── mis/
│   ├── transactions.xlsx          # Детализация_транзакций_+_услуги_2025_01_05.xlsx
│   ├── ltv_procedures.xlsx        # 5_ЛТВ по процедурам 2025 год.xlsx
│   ├── avg_ticket.xlsx            # 5_Средний_чек_на_клинику_2025.xlsx
│   ├── top_services.xlsx          # 5_Топ_услуг_2025 год старая система.xlsx
│   └── leads.xlsx                 # 5_Лиды.xlsx
├── accounting/
│   ├── cf_2024_br.xlsx            # 2024_08_БР CF.xlsx
│   ├── cf_2025_svod.xlsx          # CF_СВОД_+_КЛИНИК_АЙ_КЬЮ_янв_ноя2025_в02.xlsx
│   ├── cf_2025_clinics.xlsx       # 2025_01_БР CF (2).xlsx
│   └── cost_structure.xlsx        # 2024_11_13_отчет_по_себестоимости...xlsx
```

### 4. Запуск ETL

```bash
# Загрузить транзакции из МИС
python -m etl.pipeline transactions --file data/mis/transactions.xlsx

# Загрузить Cash Flow из 1С
python -m etl.pipeline cashflow --file data/accounting/cf_2024_br.xlsx

# Загрузить себестоимость
python -m etl.pipeline costs --file data/accounting/cost_structure.xlsx

# Загрузить лиды
python -m etl.pipeline leads --file data/mis/leads.xlsx

# Обновить витрины
python -m etl.pipeline refresh

# Или всё сразу
python -m etl.pipeline full
```

## Архитектура

```
МИС ClinicIQ (PostgreSQL) ──┐
                             ├──> ETL Python ──> DWH PostgreSQL ──> Витрины ──> BI
1С Бухгалтерия (Excel) ─────┘
```

### Схемы БД

- `raw` — сырые данные из источников
- `dwh` — звёздная схема (dimensions + facts)
- `marts` — материализованные витрины для дашбордов

### Филиалы

| Филиал | Код | ЮЛ | Визиты 2025 | Выручка 2025 | Средний чек |
|--------|-----|----|-------------|--------------|-------------|
| Таганская | taganskaya | БР | 15,223 | 366.7M | 24,089 |
| Динамо | dinamo | БР | 13,924 | 360.8M | 25,914 |
| Рублевка | rublevka | БР | 10,858 | 277.6M | 25,564 |
| Бауманская | baumanskaya | БР | 9,412 | 216.7M | 23,025 |
| Зиларт | zilart | БР | 8,927 | 214.6M | 24,045 |
| Хамовники | khamovniki | БРЦ | 5,316 | 149.3M | 28,078 |

## Роли доступа

- `role_owner` — полный доступ (CEO)
- `role_cfo` — полный доступ + экспорт
- `role_branch_mgr` — только свой филиал (RLS)
- `role_analyst` — только витрины (marts)
