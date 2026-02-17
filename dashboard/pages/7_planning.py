"""Страница «Планирование» — прогноз, сценарии, gap-анализ."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mock_data import get_data, BRANCHES, SEASONALITY
from formatters import fmt_rub, fmt_pct, fmt_num, BRANCH_COLORS, default_layout

st.header("Планирование и прогноз")

pnl = get_data("monthly_pnl")

# ── Фильтры ───────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("---")
    st.markdown("##### Параметры прогноза")

    forecast_months = st.slider("Горизонт прогноза (мес)", 3, 12, 6, key="fc_horizon")
    growth_rate = st.slider("Ожидаемый рост, %/год", -10, 30, 12, key="fc_growth")

    st.markdown("##### Сценарии")
    optimistic_pct = st.number_input("Оптимистичный, %", value=10, key="fc_opt")
    pessimistic_pct = st.number_input("Пессимистичный, %", value=-10, key="fc_pes")

# ── Данные для прогноза ────────────────────────────────────────────────

monthly_total = pnl.groupby("year_month").agg({
    "revenue_accrual": "sum",
    "ebitda": "sum",
    "materials": "sum",
    "total_payroll_direct": "sum",
    "rent": "sum",
    "marketing": "sum",
}).reset_index().sort_values("year_month")

# ── Простой прогноз с трендом и сезонностью ────────────────────────────

last_date = monthly_total["year_month"].max()
last_12 = monthly_total.tail(12)
avg_revenue = last_12["revenue_accrual"].mean()
avg_ebitda = last_12["ebitda"].mean()

future_dates = pd.date_range(last_date + pd.DateOffset(months=1), periods=forecast_months, freq="MS")
monthly_growth = (1 + growth_rate / 100) ** (1 / 12)

forecast_rows = []
for i, dt in enumerate(future_dates):
    sf = SEASONALITY.get(dt.month, 1.0)
    growth = monthly_growth ** (i + 1)
    rev_base = avg_revenue * sf * growth
    ebitda_ratio = avg_ebitda / avg_revenue if avg_revenue else 0.15

    forecast_rows.append({
        "year_month": dt,
        "revenue_base": rev_base,
        "revenue_optimistic": rev_base * (1 + optimistic_pct / 100),
        "revenue_pessimistic": rev_base * (1 + pessimistic_pct / 100),
        "ebitda_base": rev_base * ebitda_ratio,
        "ebitda_optimistic": rev_base * (1 + optimistic_pct / 100) * ebitda_ratio,
        "ebitda_pessimistic": rev_base * (1 + pessimistic_pct / 100) * ebitda_ratio,
    })

forecast = pd.DataFrame(forecast_rows)

# ── KPI прогноз ────────────────────────────────────────────────────────

fc_total_rev = forecast["revenue_base"].sum()
fc_total_ebitda = forecast["ebitda_base"].sum()
hist_total_rev = monthly_total["revenue_accrual"].sum()

c1, c2, c3 = st.columns(3)
with c1:
    st.metric(
        f"Прогноз выручки ({forecast_months} мес)",
        fmt_rub(fc_total_rev, 1),
    )
with c2:
    st.metric(
        f"Прогноз EBITDA ({forecast_months} мес)",
        fmt_rub(fc_total_ebitda, 1),
    )
with c3:
    annual_forecast = fc_total_rev / forecast_months * 12
    st.metric(
        "Годовой прогноз выручки",
        fmt_rub(annual_forecast, 1),
    )

st.divider()

# ── График: факт + прогноз с диапазоном ────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    st.subheader("Выручка: факт + прогноз")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=monthly_total["year_month"],
        y=monthly_total["revenue_accrual"],
        name="Факт",
        line=dict(color="#2563EB", width=3),
    ))

    fig.add_trace(go.Scatter(
        x=forecast["year_month"],
        y=forecast["revenue_optimistic"],
        name="Оптимистичный",
        line=dict(color="#059669", width=1, dash="dash"),
        showlegend=True,
    ))

    fig.add_trace(go.Scatter(
        x=forecast["year_month"],
        y=forecast["revenue_base"],
        name="Базовый",
        line=dict(color="#D97706", width=3, dash="dot"),
        fill="tonexty",
        fillcolor="rgba(5, 150, 105, 0.08)",
    ))

    fig.add_trace(go.Scatter(
        x=forecast["year_month"],
        y=forecast["revenue_pessimistic"],
        name="Пессимистичный",
        line=dict(color="#DC2626", width=1, dash="dash"),
        fill="tonexty",
        fillcolor="rgba(217, 119, 6, 0.08)",
    ))

    fig.update_layout(**default_layout(), height=420, yaxis_title="₽")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("EBITDA: факт + прогноз")

    fig2 = go.Figure()

    fig2.add_trace(go.Scatter(
        x=monthly_total["year_month"],
        y=monthly_total["ebitda"],
        name="Факт",
        line=dict(color="#059669", width=3),
    ))

    fig2.add_trace(go.Scatter(
        x=forecast["year_month"],
        y=forecast["ebitda_optimistic"],
        name="Оптимистичный",
        line=dict(color="#059669", width=1, dash="dash"),
    ))

    fig2.add_trace(go.Scatter(
        x=forecast["year_month"],
        y=forecast["ebitda_base"],
        name="Базовый",
        line=dict(color="#D97706", width=3, dash="dot"),
        fill="tonexty",
        fillcolor="rgba(5, 150, 105, 0.08)",
    ))

    fig2.add_trace(go.Scatter(
        x=forecast["year_month"],
        y=forecast["ebitda_pessimistic"],
        name="Пессимистичный",
        line=dict(color="#DC2626", width=1, dash="dash"),
        fill="tonexty",
        fillcolor="rgba(217, 119, 6, 0.08)",
    ))

    fig2.update_layout(**default_layout(), height=420, yaxis_title="₽")
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── Таблица прогноза ───────────────────────────────────────────────────

st.subheader("Детальный прогноз")

forecast_display = pd.DataFrame({
    "Месяц": forecast["year_month"].dt.strftime("%b %Y"),
    "Выручка (пессим.)": forecast["revenue_pessimistic"].apply(lambda x: fmt_rub(x, 1)),
    "Выручка (базовый)": forecast["revenue_base"].apply(lambda x: fmt_rub(x, 1)),
    "Выручка (оптим.)": forecast["revenue_optimistic"].apply(lambda x: fmt_rub(x, 1)),
    "EBITDA (базовый)": forecast["ebitda_base"].apply(lambda x: fmt_rub(x, 1)),
    "EBITDA маржа": (forecast["ebitda_base"] / forecast["revenue_base"] * 100).apply(lambda x: fmt_pct(x)),
})

st.dataframe(forecast_display, use_container_width=True, hide_index=True)

st.divider()

# ── Gap-анализ: план vs факт ──────────────────────────────────────────

st.subheader("Gap-анализ: план vs факт (2025)")

fact_2025 = pnl[pnl["year_month"].dt.year == 2025].copy()
fact_by_branch = fact_2025.groupby("branch_name").agg({
    "revenue_accrual": "sum",
    "ebitda": "sum",
}).reset_index()

plan_growth = 1 + growth_rate / 100
fact_2024 = pnl[pnl["year_month"].dt.year == 2024]
plan_by_branch = fact_2024.groupby("branch_name").agg({
    "revenue_accrual": "sum",
    "ebitda": "sum",
}).reset_index()
plan_by_branch["revenue_plan"] = plan_by_branch["revenue_accrual"] * plan_growth
plan_by_branch["ebitda_plan"] = plan_by_branch["ebitda"] * plan_growth

months_passed_2025 = fact_2025["year_month"].dt.month.max()
plan_by_branch["revenue_plan_ytd"] = plan_by_branch["revenue_plan"] * months_passed_2025 / 12
plan_by_branch["ebitda_plan_ytd"] = plan_by_branch["ebitda_plan"] * months_passed_2025 / 12

gap = fact_by_branch.merge(
    plan_by_branch[["branch_name", "revenue_plan_ytd", "ebitda_plan_ytd"]],
    on="branch_name",
)
gap["revenue_gap"] = gap["revenue_accrual"] - gap["revenue_plan_ytd"]
gap["revenue_gap_pct"] = gap["revenue_gap"] / gap["revenue_plan_ytd"] * 100
gap["ebitda_gap"] = gap["ebitda"] - gap["ebitda_plan_ytd"]
gap["ebitda_gap_pct"] = gap["ebitda_gap"] / gap["ebitda_plan_ytd"] * 100

gap_display = pd.DataFrame({
    "Филиал": gap["branch_name"],
    "Выручка факт": gap["revenue_accrual"].apply(lambda x: fmt_rub(x, 1)),
    "Выручка план": gap["revenue_plan_ytd"].apply(lambda x: fmt_rub(x, 1)),
    "Gap выручки": gap["revenue_gap"].apply(lambda x: fmt_rub(x, 1)),
    "Gap %": gap["revenue_gap_pct"].apply(lambda x: fmt_pct(x)),
    "EBITDA факт": gap["ebitda"].apply(lambda x: fmt_rub(x, 1)),
    "EBITDA план": gap["ebitda_plan_ytd"].apply(lambda x: fmt_rub(x, 1)),
    "Gap EBITDA %": gap["ebitda_gap_pct"].apply(lambda x: fmt_pct(x)),
})

st.dataframe(gap_display, use_container_width=True, hide_index=True)

# ── Визуализация gap ──────────────────────────────────────────────────

fig_gap = go.Figure()
fig_gap.add_trace(go.Bar(
    x=gap["branch_name"],
    y=gap["revenue_plan_ytd"],
    name="План",
    marker_color="#94a3b8",
))
fig_gap.add_trace(go.Bar(
    x=gap["branch_name"],
    y=gap["revenue_accrual"],
    name="Факт",
    marker_color=[BRANCH_COLORS.get(b, "#2563EB") for b in gap["branch_name"]],
))
fig_gap.update_layout(**default_layout(), height=380, barmode="group", yaxis_title="₽")
st.plotly_chart(fig_gap, use_container_width=True)

st.divider()

# ── Точка безубыточности ───────────────────────────────────────────────

st.subheader("Точка безубыточности по филиалам")

branch_costs = pnl.groupby("branch_name").agg({
    "revenue_accrual": "mean",
    "materials": "mean",
    "lab": "mean",
    "payroll_doctors": "mean",
    "payroll_assistants": "mean",
    "rent": "mean",
    "marketing": "mean",
    "it_costs": "mean",
    "avg_ticket": "mean",
    "payment_count": "mean",
}).reset_index()

branch_costs["fixed_costs"] = branch_costs["rent"] + branch_costs["it_costs"]
branch_costs["variable_costs"] = (
    branch_costs["materials"] + branch_costs["lab"]
    + branch_costs["payroll_doctors"] + branch_costs["payroll_assistants"]
    + branch_costs["marketing"]
)
branch_costs["variable_pct"] = branch_costs["variable_costs"] / branch_costs["revenue_accrual"]
branch_costs["contribution_margin"] = 1 - branch_costs["variable_pct"]
branch_costs["breakeven_revenue"] = branch_costs["fixed_costs"] / branch_costs["contribution_margin"]
branch_costs["breakeven_patients"] = (
    branch_costs["breakeven_revenue"] / branch_costs["avg_ticket"]
).round(0)
branch_costs["safety_margin"] = (
    (branch_costs["revenue_accrual"] - branch_costs["breakeven_revenue"])
    / branch_costs["revenue_accrual"] * 100
)

be_display = pd.DataFrame({
    "Филиал": branch_costs["branch_name"],
    "Ср. выручка/мес": branch_costs["revenue_accrual"].apply(lambda x: fmt_rub(x, 1)),
    "Постоянные расходы": branch_costs["fixed_costs"].apply(lambda x: fmt_rub(x, 1)),
    "Переменные %": branch_costs["variable_pct"].apply(lambda x: fmt_pct(x * 100)),
    "Точка безубыт.": branch_costs["breakeven_revenue"].apply(lambda x: fmt_rub(x, 1)),
    "Безубыт. пациентов": branch_costs["breakeven_patients"].apply(lambda x: fmt_num(x)),
    "Запас прочности": branch_costs["safety_margin"].apply(lambda x: fmt_pct(x)),
})

st.dataframe(be_display, use_container_width=True, hide_index=True)

col5, col6 = st.columns(2)

with col5:
    fig_be = go.Figure()
    fig_be.add_trace(go.Bar(
        x=branch_costs["branch_name"],
        y=branch_costs["breakeven_revenue"],
        name="Точка безубыточности",
        marker_color="#DC2626",
        opacity=0.7,
    ))
    fig_be.add_trace(go.Bar(
        x=branch_costs["branch_name"],
        y=branch_costs["revenue_accrual"],
        name="Средняя выручка",
        marker_color=[BRANCH_COLORS.get(b, "#2563EB") for b in branch_costs["branch_name"]],
    ))
    fig_be.update_layout(**default_layout(), height=380, barmode="group", yaxis_title="₽/мес")
    st.plotly_chart(fig_be, use_container_width=True)

with col6:
    safety = branch_costs.sort_values("safety_margin", ascending=True)
    colors = ["#DC2626" if v < 20 else "#D97706" if v < 40 else "#059669"
              for v in safety["safety_margin"]]
    fig_safety = go.Figure(go.Bar(
        x=safety["safety_margin"],
        y=safety["branch_name"],
        orientation="h",
        marker_color=colors,
        text=safety["safety_margin"].apply(lambda x: f"{x:.1f}%"),
        textposition="outside",
    ))
    fig_safety.update_layout(
        **default_layout(), height=380, showlegend=False,
        xaxis_title="Запас прочности, %",
        title="Запас прочности по филиалам",
    )
    st.plotly_chart(fig_safety, use_container_width=True)
