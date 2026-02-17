"""Утилиты форматирования, цветовые палитры, стили таблиц."""

import pandas as pd

# ── Цветовая палитра филиалов (единая на всех графиках) ────────────────

BRANCH_COLORS = {
    "Таганская":  "#2563EB",
    "Динамо":     "#7C3AED",
    "Рублёвка":   "#059669",
    "Бауманская": "#D97706",
    "Зиларт":     "#DC2626",
    "Хамовники":  "#0891B2",
}

SEVERITY_COLORS = {
    "critical": "#DC2626",
    "warning":  "#D97706",
    "info":     "#2563EB",
}

SEVERITY_ICONS = {
    "critical": "🔴",
    "warning":  "🟡",
    "info":     "🔵",
}

PLOTLY_TEMPLATE = "plotly_white"

# ── Форматирование чисел ──────────────────────────────────────────────


def fmt_rub(value, decimals=0) -> str:
    """Форматирование в рубли с разделителями тысяч."""
    if pd.isna(value):
        return "—"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.{decimals}f} млн ₽".replace(",", " ")
    if abs(value) >= 1_000:
        return f"{value / 1_000:,.{decimals}f} тыс ₽".replace(",", " ")
    return f"{value:,.{decimals}f} ₽".replace(",", " ")


def fmt_rub_full(value) -> str:
    """Полное значение в рублях с разделителями."""
    if pd.isna(value):
        return "—"
    return f"{value:,.0f} ₽".replace(",", " ")


def fmt_pct(value, decimals=1) -> str:
    """Форматирование процентов."""
    if pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}%".replace(",", " ")


def fmt_num(value, decimals=0) -> str:
    """Форматирование числа с разделителями."""
    if pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}".replace(",", " ")


def fmt_delta(value, as_pct=False) -> str:
    """Форматирование дельты со стрелкой."""
    if pd.isna(value):
        return "—"
    arrow = "▲" if value > 0 else "▼" if value < 0 else "●"
    if as_pct:
        return f"{arrow} {abs(value):.1f}%"
    return f"{arrow} {fmt_rub(abs(value))}"


def delta_color(value) -> str:
    """Цвет для дельты: зелёный если рост, красный если падение."""
    if pd.isna(value):
        return "off"
    return "normal" if value >= 0 else "inverse"


# ── Стилизация таблиц ─────────────────────────────────────────────────

def style_pnl_table(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Стиль для P&L таблицы: цветовое кодирование маржинальности."""
    money_cols = [c for c in df.columns if any(
        k in c.lower() for k in ["revenue", "выручка", "ebitda", "маржа",
                                   "материал", "фот", "аренда", "маркет",
                                   "расход"]
    )]

    def highlight_negative(val):
        if isinstance(val, (int, float)):
            if val < 0:
                return "color: #DC2626; font-weight: 600"
        return ""

    styler = df.style.applymap(highlight_negative)
    return styler


def traffic_light(val, thresholds=(0.10, 0.20)):
    """Светофор: красный < low, жёлтый < high, зелёный >= high."""
    if pd.isna(val):
        return ""
    if isinstance(val, (int, float)):
        if val < thresholds[0]:
            return "background-color: rgba(220, 38, 38, 0.15); color: #DC2626"
        if val < thresholds[1]:
            return "background-color: rgba(217, 119, 6, 0.15); color: #D97706"
        return "background-color: rgba(5, 150, 105, 0.15); color: #059669"
    return ""


# ── Plotly layout defaults ─────────────────────────────────────────────

def default_layout() -> dict:
    """Общие настройки layout для Plotly графиков."""
    return dict(
        template=PLOTLY_TEMPLATE,
        font=dict(family="Inter, system-ui, sans-serif", size=13),
        margin=dict(l=60, r=30, t=50, b=50),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        hovermode="x unified",
    )
