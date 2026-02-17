# Техническое задание на REST API интеграции

**Заказчик:** Сеть стоматологических клиник «Белая Радуга» (6 филиалов, г. Москва)
**Исполнитель:** ClinicIQ (i.cliniciq.ru)
**Дата:** 17 февраля 2026 г.
**Версия документа:** 1.0

---

## 1. Цель и контекст

«Белая Радуга» строит внутреннюю аналитическую систему (DWH + BI) для управленческого учёта, план-факт анализа и прогнозирования по всем 6 филиалам. Для этого необходимо получать данные из МИС ClinicIQ в автоматическом режиме.

**Требуется:** REST API с доступом только на чтение (read-only), позволяющий периодически выгружать данные о транзакциях, визитах, врачах, услугах, пациентах (агрегированно) и счетах.

**Филиалы:**

| # | Название     | Идентификатор в МИС |
|---|-------------|---------------------|
| 1 | Таганская   | (Таганская)         |
| 2 | Бауманская  | (Бауманская)        |
| 3 | Динамо      | (Динамо)            |
| 4 | Зиларт      | (Зиларт)            |
| 5 | Рублевка    | (Рублевка)          |
| 6 | Хамовники   | (Хамовники)         |

---

## 2. Авторизация и безопасность

### 2.1. Основной метод: OAuth 2.0 Client Credentials

Для machine-to-machine интеграции (ETL-пайплайн, без участия пользователя).

**Получение токена:**

```
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id={CLIENT_ID}
&client_secret={CLIENT_SECRET}
&scope=read
```

**Ответ:**

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "read"
}
```

**Использование:**

```
GET /api/v1/transactions?date_from=2025-01-01
Authorization: Bearer {access_token}
```

**Требования к реализации:**
- Токен действует 1 час (`expires_in: 3600`)
- `client_id` и `client_secret` выдаются администратором ClinicIQ и привязаны к конкретному tenant (организации «Белая Радуга»)
- Scope `read` -- доступ только на чтение (методы GET)
- Refresh-токен не требуется -- клиент запрашивает новый access_token при истечении

### 2.2. Альтернативный метод: API Key

Упрощённый вариант, если OAuth 2.0 избыточен для данной интеграции.

**Использование:**

```
GET /api/v1/transactions?date_from=2025-01-01
X-API-Key: {API_KEY}
```

**Требования к реализации:**
- API-ключ генерируется в панели администратора ClinicIQ
- Привязан к tenant (организации) и имеет права только на чтение
- Возможность отозвать (revoke) ключ без влияния на другие интеграции
- Рекомендуемый формат: случайная строка длиной >= 40 символов

### 2.3. Общие требования безопасности

| Требование | Описание |
|------------|----------|
| Транспорт | Только HTTPS (TLS 1.2+) |
| IP whitelist | Возможность ограничить доступ по IP-адресам (опционально) |
| Аудит | Логирование всех API-запросов (timestamp, client_id, endpoint, response_code) |
| Персональные данные | API НЕ возвращает ФИО пациентов -- только анонимизированный `patient_id` (внутренний ID или хэш) |
| Права | Только READ (GET-запросы). POST/PUT/DELETE запрещены |

---

## 3. Общие соглашения

### 3.1. Base URL

```
https://i.cliniciq.ru/api/v1
```

или выделенный поддомен:

```
https://api.cliniciq.ru/v1
```

### 3.2. Формат данных

- Формат ответов: **JSON** (`Content-Type: application/json; charset=utf-8`)
- Кодировка: **UTF-8**
- Формат дат: **ISO 8601** (`2025-01-15`, `2025-01-15T14:30:00+03:00`)
- Денежные суммы: числа с 2 десятичными знаками (`12500.00`), валюта RUB (подразумевается)
- Null-значения: `null` (не пустые строки)

### 3.3. Пагинация (cursor-based)

Все эндпоинты, возвращающие списки, используют cursor-based пагинацию:

**Параметры запроса:**

| Параметр | Тип    | По умолчанию | Описание |
|----------|--------|-------------|----------|
| `limit`  | int    | 100         | Количество записей (1-1000) |
| `cursor` | string | null        | Курсор для следующей страницы |

**Формат ответа:**

```json
{
  "data": [ ... ],
  "pagination": {
    "cursor": "eyJpZCI6MTIzNDV9",
    "has_more": true,
    "total_count": 51751
  }
}
```

- `cursor` -- непрозрачный токен, передаётся в следующий запрос
- `has_more` -- есть ли ещё данные
- `total_count` -- общее количество записей, удовлетворяющих фильтрам (опционально, может быть приблизительным)

### 3.4. Инкрементальная синхронизация

Все эндпоинты поддерживают параметр `modified_since`:

```
GET /api/v1/transactions?modified_since=2025-01-15T10:00:00+03:00
```

Возвращает записи, созданные или изменённые после указанного момента. Это позволяет загружать только дельту при регулярной синхронизации (ежедневно/еженедельно), а не весь объём данных.

**Требования:**
- Каждая запись в БД должна иметь поле `updated_at` (timestamp with timezone)
- `modified_since` фильтрует по `updated_at >= {значение}`
- Включает как новые записи, так и изменённые (например, изменение статуса счёта)

### 3.5. Коды ответов

| HTTP-код | Значение | Когда |
|----------|----------|-------|
| 200 | OK | Успешный запрос |
| 400 | Bad Request | Некорректные параметры (невалидная дата, неизвестный branch_id) |
| 401 | Unauthorized | Отсутствует или невалидный токен/ключ |
| 403 | Forbidden | Нет доступа к запрашиваемому ресурсу |
| 404 | Not Found | Ресурс не найден (конкретный doctor_id и т.п.) |
| 429 | Too Many Requests | Превышен лимит запросов |
| 500 | Internal Server Error | Ошибка на стороне сервера |

**Формат ошибки:**

```json
{
  "error": {
    "code": "INVALID_DATE_RANGE",
    "message": "date_from must be before date_to",
    "details": {
      "date_from": "2025-12-01",
      "date_to": "2025-01-01"
    }
  }
}
```

---

## 4. Эндпоинты

### 4.1. GET /api/v1/transactions

**Основной эндпоинт.** Детализация финансовых транзакций (оплаты и возвраты) с привязкой к услугам, врачам и филиалам. Аналог выгрузки «Детализация транзакций + услуги» (~51 000 строк за 2024-2025).

**Параметры запроса:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|-------------|----------|
| `date_from` | date | Да | Начало периода (включительно). ISO 8601: `2025-01-01` |
| `date_to` | date | Да | Конец периода (включительно). ISO 8601: `2025-01-31` |
| `branch_id` | int/string | Нет | Фильтр по филиалу. ID или код филиала |
| `doctor_id` | int | Нет | Фильтр по врачу |
| `operation_type` | string | Нет | `payment` (оплата) или `refund` (возврат) |
| `payment_type` | string | Нет | Тип оплаты: `card`, `cash`, `ip_artemenko`, `bonus` |
| `modified_since` | datetime | Нет | Инкрементальная синхронизация |
| `limit` | int | Нет | Размер страницы (по умолч. 100, макс. 1000) |
| `cursor` | string | Нет | Курсор пагинации |

**Пример запроса:**

```
GET /api/v1/transactions?date_from=2025-01-01&date_to=2025-01-31&branch_id=1&limit=500
Authorization: Bearer {access_token}
```

**Пример ответа:**

```json
{
  "data": [
    {
      "transaction_id": 100234,
      "transaction_date": "2025-01-15",
      "transaction_datetime": "2025-01-15T10:32:00+03:00",
      "branch": {
        "id": 1,
        "name": "Таганская",
        "code": "taganskaya"
      },
      "patient": {
        "id": "PAT-00042817",
        "age": 34,
        "age_group": "adult"
      },
      "payment_type": {
        "code": "card",
        "name": "Карта"
      },
      "operation_type": "payment",
      "invoice": {
        "id": "INV-2025-00891",
        "branch_id": 1,
        "total_amount": 45000.00,
        "debt": 0.00,
        "status": "paid",
        "discount_amount": 0.00,
        "discount_percent": 0.0
      },
      "services": [
        {
          "service_id": 301,
          "code": "A16.07.002",
          "name": "Восстановление зуба пломбой с использованием стеклоиономерных цементов",
          "category": "Терапия",
          "quantity": 1,
          "price": 8500.00,
          "discount": 0.00,
          "total": 8500.00
        }
      ],
      "doctor": {
        "id": 15,
        "name": "Иванов И.А.",
        "specialization": "Терапевт"
      },
      "visit": {
        "date": "2025-01-15",
        "type": "primary",
        "reason": "Кариес"
      },
      "amount": 8500.00,
      "created_at": "2025-01-15T10:32:00+03:00",
      "updated_at": "2025-01-15T10:32:00+03:00"
    }
  ],
  "pagination": {
    "cursor": "eyJpZCI6MTAwMjM0fQ==",
    "has_more": true,
    "total_count": 4521
  }
}
```

**Описание полей ответа:**

| Поле | Тип | Описание |
|------|-----|----------|
| `transaction_id` | int | Уникальный ID транзакции |
| `transaction_date` | date | Дата транзакции |
| `transaction_datetime` | datetime | Дата и время транзакции |
| `branch.id` | int | ID филиала |
| `branch.name` | string | Название филиала |
| `branch.code` | string | Код филиала (латиница) |
| `patient.id` | string | Анонимный ID пациента (НЕ ФИО) |
| `patient.age` | int | Возраст пациента на момент визита |
| `patient.age_group` | string | `adult` или `child` |
| `payment_type.code` | string | Код типа оплаты |
| `payment_type.name` | string | Название типа оплаты |
| `operation_type` | string | `payment` (оплата) или `refund` (возврат) |
| `invoice.id` | string | Номер счёта |
| `invoice.total_amount` | decimal | Сумма счёта |
| `invoice.debt` | decimal | Остаток задолженности |
| `invoice.status` | string | `paid`, `partial`, `unpaid`, `cancelled` |
| `invoice.discount_amount` | decimal | Сумма скидки |
| `invoice.discount_percent` | decimal | Процент скидки |
| `services[]` | array | Список услуг в транзакции |
| `services[].service_id` | int | ID услуги |
| `services[].code` | string | Код номенклатуры |
| `services[].name` | string | Наименование услуги |
| `services[].category` | string | Категория (Терапия, Хирургия, Ортопедия и др.) |
| `services[].quantity` | int | Количество |
| `services[].price` | decimal | Цена за единицу |
| `services[].discount` | decimal | Скидка на услугу |
| `services[].total` | decimal | Итого за позицию |
| `doctor.id` | int | ID врача |
| `doctor.name` | string | ФИО врача (сокращённое) |
| `doctor.specialization` | string | Специализация |
| `visit.date` | date | Дата визита |
| `visit.type` | string | `primary` (первичный) или `repeat` (повторный) |
| `visit.reason` | string | Причина обращения |
| `amount` | decimal | Сумма транзакции (может быть отрицательной для возвратов) |
| `created_at` | datetime | Дата создания записи |
| `updated_at` | datetime | Дата последнего изменения |

---

### 4.2. GET /api/v1/doctors

Справочник врачей.

**Параметры запроса:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|-------------|----------|
| `branch_id` | int | Нет | Фильтр по филиалу |
| `specialization` | string | Нет | Фильтр по специализации |
| `is_active` | boolean | Нет | Только активные (по умолч. `true`) |
| `modified_since` | datetime | Нет | Инкрементальная синхронизация |

**Пример ответа:**

```json
{
  "data": [
    {
      "doctor_id": 15,
      "full_name": "Иванов Иван Алексеевич",
      "short_name": "Иванов И.А.",
      "specialization": "Терапевт",
      "additional_specializations": ["Эндодонтист"],
      "primary_branch": {
        "id": 1,
        "name": "Таганская"
      },
      "branches": [
        { "id": 1, "name": "Таганская" },
        { "id": 3, "name": "Динамо" }
      ],
      "is_active": true,
      "hire_date": "2022-03-15",
      "updated_at": "2025-01-10T09:00:00+03:00"
    }
  ],
  "pagination": {
    "cursor": null,
    "has_more": false,
    "total_count": 47
  }
}
```

**Описание полей:**

| Поле | Тип | Описание |
|------|-----|----------|
| `doctor_id` | int | Уникальный ID врача |
| `full_name` | string | ФИО врача (полное) |
| `short_name` | string | ФИО сокращённое |
| `specialization` | string | Основная специализация |
| `additional_specializations` | string[] | Дополнительные специализации |
| `primary_branch` | object | Основной филиал |
| `branches` | object[] | Все филиалы, где принимает |
| `is_active` | boolean | Работает ли в настоящий момент |
| `hire_date` | date | Дата приёма на работу |
| `updated_at` | datetime | Дата последнего изменения |

---

### 4.3. GET /api/v1/services

Справочник (каталог) услуг с кодами и ценами.

**Параметры запроса:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|-------------|----------|
| `category` | string | Нет | Фильтр по категории (Терапия, Хирургия, Ортопедия, Ортодонтия, Гигиена, Седация, Диагностика, Консультация) |
| `is_active` | boolean | Нет | Только действующие (по умолч. `true`) |
| `search` | string | Нет | Поиск по названию (подстрока) |
| `modified_since` | datetime | Нет | Инкрементальная синхронизация |

**Пример ответа:**

```json
{
  "data": [
    {
      "service_id": 301,
      "code": "A16.07.002",
      "name": "Восстановление зуба пломбой с использованием стеклоиономерных цементов",
      "category": "Терапия",
      "subcategory": "Пломбирование",
      "base_price": 8500.00,
      "prices_by_branch": [
        { "branch_id": 1, "branch_name": "Таганская", "price": 8500.00 },
        { "branch_id": 5, "branch_name": "Рублевка", "price": 9500.00 }
      ],
      "duration_minutes": 60,
      "is_active": true,
      "updated_at": "2025-01-01T00:00:00+03:00"
    }
  ],
  "pagination": {
    "cursor": null,
    "has_more": false,
    "total_count": 412
  }
}
```

**Описание полей:**

| Поле | Тип | Описание |
|------|-----|----------|
| `service_id` | int | Уникальный ID услуги |
| `code` | string | Код номенклатуры |
| `name` | string | Полное наименование услуги |
| `category` | string | Категория услуги |
| `subcategory` | string | Подкатегория (если есть) |
| `base_price` | decimal | Базовая цена |
| `prices_by_branch` | object[] | Цены в разрезе филиалов (если различаются) |
| `duration_minutes` | int | Нормативная длительность (минут) |
| `is_active` | boolean | Действующая ли услуга |
| `updated_at` | datetime | Дата последнего изменения |

---

### 4.4. GET /api/v1/patients/stats

Агрегированная статистика по пациентам. **Персональные данные (ФИО, контакты, мед.данные) НЕ передаются.** Только анонимизированные ID и агрегаты.

**Параметры запроса:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|-------------|----------|
| `date_from` | date | Да | Начало периода |
| `date_to` | date | Да | Конец периода |
| `branch_id` | int | Нет | Фильтр по филиалу |
| `age_group` | string | Нет | `adult` или `child` |
| `group_by` | string | Нет | Группировка: `month`, `branch`, `age_group`. Можно комбинировать через запятую |

**Пример запроса:**

```
GET /api/v1/patients/stats?date_from=2025-01-01&date_to=2025-06-30&group_by=month,branch
```

**Пример ответа:**

```json
{
  "data": [
    {
      "period": "2025-01",
      "branch": {
        "id": 1,
        "name": "Таганская"
      },
      "total_patients": 412,
      "new_patients": 87,
      "returning_patients": 325,
      "retention_rate": 0.789,
      "avg_age": 36.4,
      "age_distribution": {
        "0_17": 42,
        "18_30": 98,
        "31_45": 156,
        "46_60": 78,
        "60_plus": 38
      },
      "avg_visits_per_patient": 2.3,
      "avg_revenue_per_patient": 18750.00,
      "avg_ltv": 67200.00
    }
  ]
}
```

**Описание полей:**

| Поле | Тип | Описание |
|------|-----|----------|
| `period` | string | Период (YYYY-MM) |
| `branch` | object | Филиал (если group_by включает `branch`) |
| `total_patients` | int | Всего уникальных пациентов |
| `new_patients` | int | Первичные пациенты (первый визит в клинику) |
| `returning_patients` | int | Повторные пациенты |
| `retention_rate` | decimal | Доля вернувшихся пациентов (0..1) |
| `avg_age` | decimal | Средний возраст |
| `age_distribution` | object | Распределение по возрастным группам |
| `avg_visits_per_patient` | decimal | Среднее количество визитов на пациента |
| `avg_revenue_per_patient` | decimal | Средняя выручка на пациента |
| `avg_ltv` | decimal | Средний LTV пациента |

---

### 4.5. GET /api/v1/appointments

Записи и визиты пациентов (расписание).

**Параметры запроса:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|-------------|----------|
| `date_from` | date | Да | Начало периода |
| `date_to` | date | Да | Конец периода |
| `branch_id` | int | Нет | Фильтр по филиалу |
| `doctor_id` | int | Нет | Фильтр по врачу |
| `status` | string | Нет | Статус: `scheduled`, `completed`, `cancelled`, `no_show` |
| `visit_type` | string | Нет | `primary` (первичный) или `repeat` (повторный) |
| `modified_since` | datetime | Нет | Инкрементальная синхронизация |
| `limit` | int | Нет | Размер страницы |
| `cursor` | string | Нет | Курсор пагинации |

**Пример ответа:**

```json
{
  "data": [
    {
      "appointment_id": 78412,
      "date": "2025-01-15",
      "time_start": "10:00",
      "time_end": "11:00",
      "duration_minutes": 60,
      "branch": {
        "id": 1,
        "name": "Таганская"
      },
      "doctor": {
        "id": 15,
        "name": "Иванов И.А.",
        "specialization": "Терапевт"
      },
      "patient": {
        "id": "PAT-00042817",
        "age": 34,
        "age_group": "adult"
      },
      "visit_type": "primary",
      "reason": "Кариес",
      "status": "completed",
      "source": "website",
      "created_at": "2025-01-13T15:20:00+03:00",
      "updated_at": "2025-01-15T11:05:00+03:00"
    }
  ],
  "pagination": {
    "cursor": "eyJpZCI6Nzg0MTJ9",
    "has_more": true,
    "total_count": 8934
  }
}
```

**Описание полей:**

| Поле | Тип | Описание |
|------|-----|----------|
| `appointment_id` | int | Уникальный ID записи |
| `date` | date | Дата визита |
| `time_start` | string | Время начала (HH:MM) |
| `time_end` | string | Время окончания (HH:MM) |
| `duration_minutes` | int | Длительность визита (минут) |
| `branch` | object | Филиал |
| `doctor` | object | Врач |
| `patient.id` | string | Анонимный ID пациента |
| `patient.age` | int | Возраст |
| `patient.age_group` | string | `adult` / `child` |
| `visit_type` | string | `primary` (первичный) / `repeat` (повторный) |
| `reason` | string | Причина обращения |
| `status` | string | `scheduled`, `completed`, `cancelled`, `no_show` |
| `source` | string | Источник записи: `website`, `phone`, `walk_in`, `referral` |
| `created_at` | datetime | Дата создания записи |
| `updated_at` | datetime | Дата последнего изменения |

---

### 4.6. GET /api/v1/branches

Справочник филиалов.

**Параметры запроса:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|-------------|----------|
| `is_active` | boolean | Нет | Только активные (по умолч. `true`) |

**Пример ответа:**

```json
{
  "data": [
    {
      "branch_id": 1,
      "name": "Таганская",
      "code": "taganskaya",
      "address": "115172, Москва, Котельническая наб, 25, стр.1",
      "phone": "+7 (495) 123-45-67",
      "chairs_count": 5,
      "working_hours": {
        "monday": "09:00-21:00",
        "tuesday": "09:00-21:00",
        "wednesday": "09:00-21:00",
        "thursday": "09:00-21:00",
        "friday": "09:00-21:00",
        "saturday": "10:00-18:00",
        "sunday": null
      },
      "doctors_count": 12,
      "is_active": true,
      "opened_date": "2019-06-01",
      "updated_at": "2025-01-01T00:00:00+03:00"
    }
  ],
  "pagination": {
    "cursor": null,
    "has_more": false,
    "total_count": 6
  }
}
```

**Описание полей:**

| Поле | Тип | Описание |
|------|-----|----------|
| `branch_id` | int | Уникальный ID филиала |
| `name` | string | Название |
| `code` | string | Код (латиница) |
| `address` | string | Адрес |
| `phone` | string | Телефон |
| `chairs_count` | int | Количество стоматологических кресел |
| `working_hours` | object | Режим работы по дням |
| `doctors_count` | int | Количество активных врачей |
| `is_active` | boolean | Активен ли филиал |
| `opened_date` | date | Дата открытия |
| `updated_at` | datetime | Дата последнего изменения |

---

### 4.7. GET /api/v1/invoices

Счета на оплату.

**Параметры запроса:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|-------------|----------|
| `date_from` | date | Да | Начало периода (дата создания счёта) |
| `date_to` | date | Да | Конец периода |
| `branch_id` | int | Нет | Фильтр по филиалу |
| `doctor_id` | int | Нет | Фильтр по врачу |
| `status` | string | Нет | `paid`, `partial`, `unpaid`, `cancelled` |
| `modified_since` | datetime | Нет | Инкрементальная синхронизация |
| `limit` | int | Нет | Размер страницы |
| `cursor` | string | Нет | Курсор пагинации |

**Пример ответа:**

```json
{
  "data": [
    {
      "invoice_id": "INV-2025-00891",
      "created_date": "2025-01-15",
      "branch": {
        "id": 1,
        "name": "Таганская"
      },
      "patient": {
        "id": "PAT-00042817",
        "age_group": "adult"
      },
      "doctor": {
        "id": 15,
        "name": "Иванов И.А."
      },
      "items": [
        {
          "service_id": 301,
          "service_name": "Восстановление зуба пломбой",
          "quantity": 1,
          "unit_price": 8500.00,
          "discount_percent": 0.0,
          "discount_amount": 0.00,
          "total": 8500.00
        }
      ],
      "subtotal": 8500.00,
      "discount_total": 0.00,
      "total_amount": 8500.00,
      "paid_amount": 8500.00,
      "debt": 0.00,
      "status": "paid",
      "payments": [
        {
          "payment_date": "2025-01-15",
          "amount": 8500.00,
          "payment_type": "card"
        }
      ],
      "created_at": "2025-01-15T10:30:00+03:00",
      "updated_at": "2025-01-15T10:32:00+03:00"
    }
  ],
  "pagination": {
    "cursor": "eyJpZCI6Ijg5MSJ9",
    "has_more": true,
    "total_count": 12400
  }
}
```

**Описание полей:**

| Поле | Тип | Описание |
|------|-----|----------|
| `invoice_id` | string | Номер счёта |
| `created_date` | date | Дата создания счёта |
| `branch` | object | Филиал |
| `patient.id` | string | Анонимный ID пациента |
| `doctor` | object | Лечащий врач |
| `items[]` | array | Позиции счёта |
| `items[].service_id` | int | ID услуги |
| `items[].service_name` | string | Наименование |
| `items[].quantity` | int | Количество |
| `items[].unit_price` | decimal | Цена за единицу |
| `items[].discount_percent` | decimal | Процент скидки |
| `items[].discount_amount` | decimal | Сумма скидки |
| `items[].total` | decimal | Итого по позиции |
| `subtotal` | decimal | Сумма до скидок |
| `discount_total` | decimal | Общая сумма скидок |
| `total_amount` | decimal | Итого к оплате |
| `paid_amount` | decimal | Оплачено |
| `debt` | decimal | Задолженность |
| `status` | string | `paid`, `partial`, `unpaid`, `cancelled` |
| `payments[]` | array | Список проведённых оплат |
| `created_at` | datetime | Дата создания |
| `updated_at` | datetime | Дата последнего изменения |

---

## 5. Нефункциональные требования

### 5.1. Rate Limiting

| Параметр | Значение |
|----------|----------|
| Лимит запросов | Не менее 100 запросов/минуту на один API-ключ |
| Заголовки ответа | `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` |
| При превышении | HTTP 429 с `Retry-After` заголовком |

### 5.2. Производительность

| Параметр | Целевое значение |
|----------|-----------------|
| Время ответа (p95) | <= 2 секунды для запросов до 1000 записей |
| Время ответа (p99) | <= 5 секунд |
| Максимальный размер ответа | 10 МБ |
| Доступность (SLA) | >= 99.5% |

### 5.3. Объёмы данных (ожидаемые)

| Эндпоинт | Ожидаемый объём | Частота запросов |
|----------|----------------|-----------------|
| `/transactions` | ~50 000 записей/год | Ежедневно (инкремент) |
| `/doctors` | ~50 записей | Еженедельно |
| `/services` | ~400 записей | Еженедельно |
| `/patients/stats` | Агрегаты | Еженедельно |
| `/appointments` | ~30 000 записей/год | Ежедневно (инкремент) |
| `/branches` | 6 записей | Ежемесячно |
| `/invoices` | ~15 000 записей/год | Ежедневно (инкремент) |

### 5.4. Версионирование API

- Версия в URL: `/api/v1/...`
- При критических изменениях -- новая версия `/api/v2/...`
- Старая версия поддерживается не менее 6 месяцев после выхода новой

### 5.5. Webhook (опционально, но желательно)

Push-уведомления об изменениях для real-time синхронизации.

**Регистрация:**

```
POST /api/v1/webhooks
Content-Type: application/json
Authorization: Bearer {access_token}

{
  "url": "https://analytics.belayaraduga.ru/webhook/cliniciq",
  "events": ["transaction.created", "transaction.updated", "appointment.created", "appointment.updated"],
  "secret": "webhook_signing_secret_here"
}
```

**Формат уведомления:**

```json
{
  "event": "transaction.created",
  "timestamp": "2025-01-15T10:32:05+03:00",
  "data": {
    "transaction_id": 100234,
    "branch_id": 1,
    "amount": 8500.00
  },
  "signature": "sha256=abc123..."
}
```

**Типы событий:**

| Событие | Описание |
|---------|----------|
| `transaction.created` | Новая транзакция (оплата/возврат) |
| `transaction.updated` | Изменение транзакции |
| `appointment.created` | Новая запись |
| `appointment.updated` | Изменение записи (отмена, перенос) |
| `appointment.completed` | Визит завершён |
| `invoice.created` | Новый счёт |
| `invoice.paid` | Счёт оплачен |
| `doctor.updated` | Изменение данных врача |

---

## 6. Сценарий интеграции

Типичный сценарий ETL-загрузки:

```
1. [ETL] POST /oauth/token --> получить access_token
2. [ETL] GET /api/v1/branches --> загрузить справочник филиалов
3. [ETL] GET /api/v1/doctors --> загрузить справочник врачей
4. [ETL] GET /api/v1/services --> загрузить каталог услуг
5. [ETL] GET /api/v1/transactions?date_from=...&date_to=...&limit=1000
         --> постранично загрузить все транзакции за период
6. [ETL] GET /api/v1/appointments?date_from=...&date_to=...&limit=1000
         --> постранично загрузить все визиты
7. [ETL] GET /api/v1/invoices?date_from=...&date_to=...&limit=1000
         --> постранично загрузить все счета
8. [ETL] GET /api/v1/patients/stats?date_from=...&date_to=...&group_by=month,branch
         --> загрузить агрегированную статистику по пациентам
```

**Ежедневный инкремент (после первичной загрузки):**

```
1. [ETL] POST /oauth/token
2. [ETL] GET /api/v1/transactions?modified_since={last_sync_timestamp}&limit=1000
3. [ETL] GET /api/v1/appointments?modified_since={last_sync_timestamp}&limit=1000
4. [ETL] GET /api/v1/invoices?modified_since={last_sync_timestamp}&limit=1000
```

---

## 7. Требования к документации API

При реализации API просим предоставить:

1. **OpenAPI (Swagger) спецификацию** -- файл `openapi.yaml` (версия 3.0+)
2. **Sandbox/Staging окружение** -- тестовый стенд с демо-данными для отладки интеграции
3. **Postman-коллекцию** -- готовую коллекцию запросов для тестирования
4. **Changelog** -- лог изменений API при каждом обновлении

---

## 8. Контакты

| Роль | Контакт |
|------|---------|
| Заказчик (аналитика) | [указать email/телефон] |
| Техподдержка ClinicIQ | support@cliniciq.ru, +7 800 555 29 81 |

---

## Приложение A: Маппинг полей API -> DWH

Соответствие полей API полям в аналитическом хранилище заказчика:

| Поле API (transactions) | Поле DWH (fact_transactions) | Комментарий |
|-------------------------|------------------------------|-------------|
| `transaction_date` | `transaction_date` | Прямой маппинг |
| `branch.id` | `branch_id` | Через dim_branch |
| `patient.id` | `patient_hash` | API возвращает анонимный ID |
| `patient.age` | `patient_age` | Прямой маппинг |
| `patient.age_group` | `is_child` | adult -> false, child -> true |
| `payment_type.code` | `payment_type_id` | Через dim_payment_type |
| `operation_type` | `operation_type` | payment -> "Оплата", refund -> "Возврат оплаты" |
| `invoice.total_amount` | `invoice_amount` | Прямой маппинг |
| `invoice.debt` | `invoice_debt` | Прямой маппинг |
| `services[0].name` | `service_name` | Первая услуга в счёте |
| `services[0].service_id` | `service_id` | Через dim_service |
| `doctor.id` | `doctor_id` | Через dim_doctor |
| `visit.type` | `is_primary_visit` | primary -> true, repeat -> false |
| `amount` | `transaction_amount` | Прямой маппинг |

## Приложение B: Приоритеты реализации

Если невозможно реализовать все эндпоинты одновременно, рекомендуемый порядок:

| Приоритет | Эндпоинт | Обоснование |
|-----------|----------|-------------|
| **P0 (критично)** | `/transactions` | Основной источник данных для P&L, KPI, среднего чека |
| **P0 (критично)** | `/doctors` | Необходим для KPI врачей |
| **P0 (критично)** | `/branches` | Необходим для разбивки по филиалам |
| **P1 (важно)** | `/services` | Каталог услуг для экономики услуг |
| **P1 (важно)** | `/invoices` | Анализ скидок, дебиторской задолженности |
| **P2 (желательно)** | `/appointments` | Анализ загрузки, конверсии, no-show |
| **P2 (желательно)** | `/patients/stats` | Когортный анализ, LTV |
