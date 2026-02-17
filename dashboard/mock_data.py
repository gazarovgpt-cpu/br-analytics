"""Генератор реалистичных демо-данных для дашборда Белая Радуга.

Данные основаны на структуре витрин из sql/04_marts.sql.
Масштаб: ~1.6 млрд руб/год, 6 филиалов, ~63K визитов/год.
"""

import pandas as pd
import numpy as np
from datetime import date

np.random.seed(42)

# ── Константы ──────────────────────────────────────────────────────────

BRANCHES = {
    1: "Таганская",
    2: "Динамо",
    3: "Рублёвка",
    4: "Бауманская",
    5: "Зиларт",
    6: "Хамовники",
}

BRANCH_WEIGHTS = {
    1: 1.25,   # Таганская — флагман
    2: 1.10,
    3: 0.95,
    4: 0.85,
    5: 0.80,
    6: 1.05,
}

SPECIALIZATIONS = [
    "Терапевт",
    "Хирург",
    "Ортопед",
    "Ортодонт",
    "Детский стоматолог",
    "Пародонтолог",
    "Гигиенист",
]

DOCTOR_NAMES = [
    "Иванов А.С.", "Петрова М.В.", "Сидоров К.Н.", "Козлова Е.А.",
    "Морозов Д.И.", "Новикова О.П.", "Волков Р.Г.", "Соколова Т.Л.",
    "Лебедев И.М.", "Кузнецова Н.Д.", "Попов В.Е.", "Егорова А.Ю.",
    "Орлов С.В.", "Фёдорова И.К.", "Михайлов П.А.", "Белова Л.С.",
    "Тарасов А.В.", "Жукова М.Е.", "Григорьев Н.П.", "Андреева С.Д.",
    "Никитин О.А.", "Захарова В.И.", "Романов Д.С.", "Павлова Е.Н.",
    "Семёнов К.В.", "Алексеева Т.Г.", "Макаров И.Л.", "Дмитриева О.М.",
    "Степанов А.Р.", "Яковлева Н.С.",
]

SERVICES = {
    "Терапия": [
        ("Лечение кариеса", 8500, 0.62),
        ("Лечение пульпита", 18000, 0.55),
        ("Эндодонтическое лечение", 25000, 0.50),
        ("Реставрация зуба", 15000, 0.58),
        ("Пломбирование", 6000, 0.65),
    ],
    "Хирургия": [
        ("Удаление зуба простое", 5000, 0.70),
        ("Удаление зуба сложное", 12000, 0.60),
        ("Имплантация", 55000, 0.45),
        ("Синус-лифтинг", 45000, 0.42),
        ("Костная пластика", 35000, 0.40),
    ],
    "Ортопедия": [
        ("Коронка металлокерамика", 22000, 0.48),
        ("Коронка цирконий", 38000, 0.50),
        ("Винир E-max", 45000, 0.52),
        ("Вкладка", 18000, 0.50),
    ],
    "Ортодонтия": [
        ("Брекеты металлические", 85000, 0.55),
        ("Брекеты керамические", 120000, 0.52),
        ("Элайнеры", 250000, 0.48),
    ],
    "Гигиена": [
        ("Проф. гигиена полости рта", 7000, 0.75),
        ("Отбеливание", 25000, 0.70),
    ],
    "Диагностика": [
        ("Консультация", 2000, 0.85),
        ("Рентген (прицельный)", 800, 0.80),
        ("КТ челюсти", 5000, 0.65),
        ("Панорамный снимок", 2500, 0.72),
    ],
    "Детская стоматология": [
        ("Лечение молочного зуба", 5500, 0.60),
        ("Серебрение", 2000, 0.80),
        ("Герметизация фиссур", 3500, 0.72),
    ],
}

MONTHS_24 = pd.date_range("2024-01-01", "2025-12-01", freq="MS")

SEASONALITY = {
    1: 0.82,   # Январь — праздники
    2: 0.95,
    3: 1.08,   # Март — пик
    4: 1.04,
    5: 1.02,
    6: 0.88,   # Лето — спад
    7: 0.78,
    8: 0.82,
    9: 1.00,
    10: 1.12,  # Осень — пик
    11: 1.10,
    12: 1.02,
}

CF_EXPENSE_ITEMS = [
    ("Операционная деятельность", "Выручка от услуг", "inflow"),
    ("Операционная деятельность", "Материалы стоматологические", "outflow"),
    ("Операционная деятельность", "Лабораторные работы", "outflow"),
    ("Операционная деятельность", "ФОТ врачи", "outflow"),
    ("Операционная деятельность", "ФОТ ассистенты", "outflow"),
    ("Операционная деятельность", "ФОТ администрация", "outflow"),
    ("Операционная деятельность", "Аренда", "outflow"),
    ("Операционная деятельность", "Маркетинг и реклама", "outflow"),
    ("Операционная деятельность", "IT и ПО (Клиник Айкью)", "outflow"),
    ("Операционная деятельность", "Коммунальные платежи", "outflow"),
    ("Операционная деятельность", "Хозяйственные расходы", "outflow"),
    ("Операционная деятельность", "Налоги и взносы", "outflow"),
    ("Инвестиционная деятельность", "Оборудование", "outflow"),
    ("Инвестиционная деятельность", "Ремонт помещений", "outflow"),
    ("Финансовая деятельность", "Займы полученные", "inflow"),
    ("Финансовая деятельность", "Погашение займов", "outflow"),
]


# ── Генераторы ─────────────────────────────────────────────────────────

def _seasonal_factor(month: int) -> float:
    return SEASONALITY.get(month, 1.0)


def _growth_factor(dt: pd.Timestamp) -> float:
    """Рост ~12% годовых: месячный множитель от начала периода."""
    months_from_start = (dt.year - 2024) * 12 + dt.month - 1
    return 1.0 + 0.01 * months_from_start


def generate_monthly_pnl() -> pd.DataFrame:
    """Генерация помесячного P&L по филиалам (витрина marts.monthly_pnl)."""
    base_monthly_revenue = 22_000_000  # базовая выручка на филиал/мес

    rows = []
    for dt in MONTHS_24:
        sf = _seasonal_factor(dt.month)
        gf = _growth_factor(dt)
        for bid, bname in BRANCHES.items():
            bw = BRANCH_WEIGHTS[bid]
            noise = np.random.normal(1.0, 0.05)

            revenue = base_monthly_revenue * bw * sf * gf * noise
            refunds = revenue * np.random.uniform(0.01, 0.03)
            net_revenue = revenue - refunds
            avg_ticket = np.random.normal(14000, 2000) * bw
            unique_patients = int(net_revenue / avg_ticket)
            payment_count = int(unique_patients * np.random.uniform(1.2, 1.6))
            primary_visits = int(unique_patients * np.random.uniform(0.25, 0.40))

            materials = net_revenue * np.random.uniform(0.08, 0.12)
            lab = net_revenue * np.random.uniform(0.04, 0.07)
            gross_margin = net_revenue - materials - lab

            payroll_doctors = net_revenue * np.random.uniform(0.25, 0.32)
            payroll_assistants = net_revenue * np.random.uniform(0.06, 0.09)
            total_payroll = payroll_doctors + payroll_assistants

            rent = np.random.normal(1_800_000, 200_000) * bw
            marketing = net_revenue * np.random.uniform(0.04, 0.08)
            it_costs = np.random.normal(180_000, 30_000)

            ebitda = net_revenue - materials - lab - total_payroll - rent - marketing - it_costs

            rows.append({
                "year_month": dt.date(),
                "branch_id": bid,
                "branch_name": bname,
                "revenue_accrual": round(net_revenue),
                "revenue_cash": round(net_revenue * np.random.uniform(0.92, 0.98)),
                "gross_revenue": round(revenue),
                "refunds": round(refunds),
                "avg_ticket": round(avg_ticket),
                "unique_patients": unique_patients,
                "payment_count": payment_count,
                "primary_visits": primary_visits,
                "materials": round(materials),
                "lab": round(lab),
                "gross_margin": round(gross_margin),
                "payroll_doctors": round(payroll_doctors),
                "payroll_assistants": round(payroll_assistants),
                "total_payroll_direct": round(total_payroll),
                "rent": round(rent),
                "marketing": round(marketing),
                "it_costs": round(it_costs),
                "ebitda": round(ebitda),
            })

    df = pd.DataFrame(rows)
    df["year_month"] = pd.to_datetime(df["year_month"])
    return df


def generate_doctor_kpi() -> pd.DataFrame:
    """Генерация KPI врачей помесячно (витрина marts.doctor_kpi)."""
    doctors = []
    for i, name in enumerate(DOCTOR_NAMES):
        branch_id = (i % 6) + 1
        spec = SPECIALIZATIONS[i % len(SPECIALIZATIONS)]
        base_revenue = np.random.uniform(1_500_000, 4_500_000)
        doctors.append((i + 1, name, spec, branch_id, base_revenue))

    rows = []
    for dt in MONTHS_24:
        sf = _seasonal_factor(dt.month)
        gf = _growth_factor(dt)
        for doc_id, name, spec, branch_id, base_rev in doctors:
            noise = np.random.normal(1.0, 0.12)
            revenue = base_rev * sf * gf * noise
            if revenue < 0:
                revenue = base_rev * 0.3

            visit_count = int(revenue / np.random.uniform(10000, 20000))
            unique_patients = int(visit_count * np.random.uniform(0.65, 0.85))
            primary_visits = int(unique_patients * np.random.uniform(0.20, 0.40))
            avg_ticket = revenue / max(visit_count, 1)
            workdays = np.random.randint(18, 23)
            revenue_per_workday = revenue / workdays

            rows.append({
                "year_month": dt.date(),
                "doctor_id": doc_id,
                "doctor_name": name,
                "specialization": spec,
                "branch_id": branch_id,
                "branch_name": BRANCHES[branch_id],
                "revenue": round(revenue),
                "visit_count": visit_count,
                "unique_patients": unique_patients,
                "primary_visits": primary_visits,
                "avg_ticket": round(avg_ticket),
                "revenue_per_workday": round(revenue_per_workday),
            })

    df = pd.DataFrame(rows)
    df["year_month"] = pd.to_datetime(df["year_month"])
    return df


def generate_branch_comparison() -> pd.DataFrame:
    """Генерация данных для сравнения филиалов (витрина marts.branch_comparison)."""
    pnl = generate_monthly_pnl()
    bc = pnl.groupby(["year_month", "branch_id", "branch_name"]).agg({
        "gross_revenue": "sum",
        "revenue_accrual": "sum",
        "payment_count": "sum",
        "unique_patients": "sum",
        "primary_visits": "sum",
        "avg_ticket": "mean",
    }).reset_index()
    bc.rename(columns={"gross_revenue": "revenue", "revenue_accrual": "net_revenue"}, inplace=True)

    bc["children_revenue"] = (bc["revenue"] * np.random.uniform(0.12, 0.22, len(bc))).round()
    bc["adult_revenue"] = bc["revenue"] - bc["children_revenue"]
    bc["payments"] = bc["payment_count"]
    return bc


def generate_service_economics() -> pd.DataFrame:
    """Генерация экономики услуг (витрина marts.service_economics)."""
    rows = []
    for category, services in SERVICES.items():
        for svc_name, base_price, margin_pct in services:
            for bid, bname in BRANCHES.items():
                bw = BRANCH_WEIGHTS[bid]
                count = int(np.random.uniform(80, 400) * bw)
                avg_price = base_price * np.random.uniform(0.90, 1.10)
                total_revenue = count * avg_price
                material_cost = avg_price * np.random.uniform(0.05, 0.15)
                doctor_pay = avg_price * np.random.uniform(0.25, 0.35)
                actual_margin = margin_pct * np.random.uniform(0.90, 1.10)

                rows.append({
                    "service_name": svc_name,
                    "category": category,
                    "branch_id": bid,
                    "branch_name": bname,
                    "service_count": count,
                    "total_revenue": round(total_revenue),
                    "avg_price": round(avg_price),
                    "material_cost": round(material_cost),
                    "doctor_pay": round(doctor_pay),
                    "margin_pct": round(actual_margin * 100, 1),
                })

    return pd.DataFrame(rows)


def generate_cashflow() -> pd.DataFrame:
    """Генерация данных денежного потока (CF по статьям помесячно)."""
    rows = []
    for dt in MONTHS_24:
        sf = _seasonal_factor(dt.month)
        gf = _growth_factor(dt)
        for bid, bname in BRANCHES.items():
            bw = BRANCH_WEIGHTS[bid]
            base = 22_000_000 * bw * sf * gf

            amounts = {
                "Выручка от услуг": base * np.random.uniform(0.93, 0.99),
                "Материалы стоматологические": base * np.random.uniform(0.08, 0.12),
                "Лабораторные работы": base * np.random.uniform(0.04, 0.07),
                "ФОТ врачи": base * np.random.uniform(0.25, 0.32),
                "ФОТ ассистенты": base * np.random.uniform(0.06, 0.09),
                "ФОТ администрация": base * np.random.uniform(0.05, 0.07),
                "Аренда": np.random.normal(1_800_000, 150_000) * bw,
                "Маркетинг и реклама": base * np.random.uniform(0.04, 0.08),
                "IT и ПО (Клиник Айкью)": np.random.normal(180_000, 20_000),
                "Коммунальные платежи": np.random.normal(120_000, 20_000) * bw,
                "Хозяйственные расходы": np.random.normal(80_000, 15_000) * bw,
                "Налоги и взносы": base * np.random.uniform(0.06, 0.09),
                "Оборудование": (np.random.exponential(200_000) if np.random.random() < 0.3 else 0),
                "Ремонт помещений": (np.random.exponential(150_000) if np.random.random() < 0.2 else 0),
                "Займы полученные": (np.random.exponential(500_000) if np.random.random() < 0.1 else 0),
                "Погашение займов": (np.random.normal(200_000, 50_000) if np.random.random() < 0.15 else 0),
            }

            for cf_group, item_name, direction in CF_EXPENSE_ITEMS:
                amt = amounts.get(item_name, 0)
                if amt <= 0:
                    continue
                rows.append({
                    "year_month": dt.date(),
                    "branch_id": bid,
                    "branch_name": bname,
                    "cf_group": cf_group,
                    "line_item": item_name,
                    "direction": direction,
                    "amount": round(abs(amt)),
                })

    df = pd.DataFrame(rows)
    df["year_month"] = pd.to_datetime(df["year_month"])
    return df


def generate_alerts() -> pd.DataFrame:
    """Генерация алертов оптимизации (витрина marts.alerts)."""
    alert_templates = [
        ("margin_drop", "warning", "Маржинальность",
         "Снижение маржинальности на {val:.1f}% за месяц",
         "Проверить структуру расходов и ценообразование"),
        ("material_spike", "critical", "Расход материалов",
         "Рост расходов на материалы на {val:.0f}% к пред. месяцу",
         "Провести аудит закупок, проверить поставщиков"),
        ("revenue_drop", "warning", "Выручка",
         "Падение выручки на {val:.1f}% к плану",
         "Усилить маркетинг, проверить загрузку врачей"),
        ("low_primary", "info", "Первичные визиты",
         "Доля первичных визитов ниже {val:.0f}%",
         "Проверить эффективность каналов привлечения"),
        ("high_refund", "warning", "Возвраты",
         "Уровень возвратов {val:.1f}% — выше нормы",
         "Проверить качество услуг и работу с рекламациями"),
        ("payroll_overrun", "critical", "ФОТ",
         "ФОТ превышает {val:.0f}% от выручки",
         "Пересмотреть мотивацию и штатное расписание"),
    ]

    rows = []
    alert_id = 0
    for dt in MONTHS_24[-6:]:
        for bid, bname in BRANCHES.items():
            if np.random.random() < 0.25:
                tmpl = alert_templates[np.random.randint(0, len(alert_templates))]
                val = np.random.uniform(5, 25)
                alert_id += 1
                rows.append({
                    "alert_id": alert_id,
                    "created_at": dt,
                    "year_month": dt.date(),
                    "branch_id": bid,
                    "branch_name": bname,
                    "alert_type": tmpl[0],
                    "severity": tmpl[1],
                    "metric_name": tmpl[2],
                    "metric_value": round(val, 2),
                    "threshold_value": round(val * 0.8, 2),
                    "description": tmpl[3].format(val=val),
                    "recommendation": tmpl[4],
                })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["year_month"] = pd.to_datetime(df["year_month"])
    return df


# ── Кэшируемые точки входа ────────────────────────────────────────────

_cache: dict[str, pd.DataFrame] = {}


def get_data(name: str) -> pd.DataFrame:
    """Получить DataFrame по имени с кэшированием."""
    if name not in _cache:
        generators = {
            "monthly_pnl": generate_monthly_pnl,
            "doctor_kpi": generate_doctor_kpi,
            "branch_comparison": generate_branch_comparison,
            "service_economics": generate_service_economics,
            "cashflow": generate_cashflow,
            "alerts": generate_alerts,
        }
        if name not in generators:
            raise ValueError(f"Unknown dataset: {name}")
        _cache[name] = generators[name]()
    return _cache[name].copy()
