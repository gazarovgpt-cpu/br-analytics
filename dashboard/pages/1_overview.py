"""Страница «Обзор» — KPI, тренды, светофор, алерты."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mock_data import get_data, BRANCHES
from formatters import (
    fmt_rub, fmt_num, fmt_pct, delta_color,
    BRANCH_COLORS, SEVERITY_COLORS, SEVERITY_ICONS,
    default_layout,
)

st.header("Обзор")

# ── Загрузка данных ────────────────────────────────────────────────────

pnl = get_data("monthly_pnl")
alerts = get_data("alerts")

# ── Глобальные фильтры (sidebar) ──────────────────────────────────────

with st.sidebar:
    st.markdown("---")
    st.markdown("##### Фильтры")
    all_months = sorted(pnl["year_month"].unique())
    period = st.select_slider(
        "Период",
        options=all_months,
        value=(all_months[0], all_months[-1]),
        format_func=lambda x: pd.Timestamp(x).strftime("%b %Y"),
    )

pnl = pnl[(pnl["year_month"] >= period[0]) & (pnl["year_month"] <= period[1])]

# ── KPI-карточки ───────────────────────────────────────────────────────

latest = pnl["year_month"].max()
prev = latest - pd.DateOffset(months=1)

cur = pnl[pnl["year_month"] == latest]
prv = pnl[pnl["year_month"] == prev]

revenue_cur = cur["revenue_accrual"].sum()
revenue_prv = prv["revenue_accrual"].sum()
ebitda_cur = cur["ebitda"].sum()
ebitda_prv = prv["ebitda"].sum()
ticket_cur = cur["avg_ticket"].mean()
ticket_prv = prv["avg_ticket"].mean()
patients_cur = cur["unique_patients"].sum()
patients_prv = prv["unique_patients"].sum()

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(
        "Выручка",
        fmt_rub(revenue_cur, 1),
        f"{(revenue_cur / revenue_prv - 1) * 100:+.1f}%" if revenue_prv else None,
    )
with c2:
    st.metric(
        "EBITDA",
        fmt_rub(ebitda_cur, 1),
        f"{(ebitda_cur / ebitda_prv - 1) * 100:+.1f}%" if ebitda_prv else None,
    )
with c3:
    st.metric(
        "Средний чек",
        fmt_rub(ticket_cur),
        f"{(ticket_cur / ticket_prv - 1) * 100:+.1f}%" if ticket_prv else None,
    )
with c4:
    st.metric(
        "Пациенты",
        fmt_num(patients_cur),
        f"{(patients_cur / patients_prv - 1) * 100:+.1f}%" if patients_prv else None,
    )

st.divider()

# ── Тренд выручки и EBITDA ────────────────────────────────────────────

monthly_total = pnl.groupby("year_month").agg({
    "revenue_accrual": "sum",
    "ebitda": "sum",
}).reset_index()

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Тренд выручки и EBITDA")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly_total["year_month"], y=monthly_total["revenue_accrual"],
        name="Выручка", line=dict(color="#2563EB", width=3),
        fill="tozeroy", fillcolor="rgba(37, 99, 235, 0.08)",
    ))
    fig.add_trace(go.Scatter(
        x=monthly_total["year_month"], y=monthly_total["ebitda"],
        name="EBITDA", line=dict(color="#059669", width=3),
        fill="tozeroy", fillcolor="rgba(5, 150, 105, 0.08)",
    ))
    fig.update_layout(
        **default_layout(),
        yaxis_title="₽",
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Структура выручки по филиалам ──────────────────────────────────────

with col_right:
    st.subheader("Выручка по филиалам")
    fig2 = px.bar(
        pnl.sort_values("year_month"),
        x="year_month", y="revenue_accrual",
        color="branch_name",
        color_discrete_map=BRANCH_COLORS,
        labels={"revenue_accrual": "Выручка, ₽", "year_month": "", "branch_name": "Филиал"},
    )
    fig2.update_layout(**default_layout(), height=380, barmode="stack")
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── Таблица-светофор по филиалам ───────────────────────────────────────

st.subheader("Ключевые показатели по филиалам")

branch_summary = pnl.groupby("branch_name").agg({
    "revenue_accrual": "sum",
    "ebitda": "sum",
    "avg_ticket": "mean",
    "unique_patients": "sum",
    "primary_visits": "sum",
    "materials": "sum",
    "total_payroll_direct": "sum",
}).reset_index()

branch_summary["ebitda_margin"] = branch_summary["ebitda"] / branch_summary["revenue_accrual"]
branch_summary["cost_ratio"] = (
    (branch_summary["materials"] + branch_summary["total_payroll_direct"])
    / branch_summary["revenue_accrual"]
)
branch_summary["primary_share"] = branch_summary["primary_visits"] / branch_summary["unique_patients"]

display_df = pd.DataFrame({
    "Филиал": branch_summary["branch_name"],
    "Выручка": branch_summary["revenue_accrual"].apply(lambda x: fmt_rub(x, 1)),
    "EBITDA": branch_summary["ebitda"].apply(lambda x: fmt_rub(x, 1)),
    "Маржа EBITDA": branch_summary["ebitda_margin"].apply(lambda x: fmt_pct(x * 100)),
    "Ср. чек": branch_summary["avg_ticket"].apply(lambda x: fmt_rub(x)),
    "Пациенты": branch_summary["unique_patients"].apply(lambda x: fmt_num(x)),
    "Доля первичных": branch_summary["primary_share"].apply(lambda x: fmt_pct(x * 100)),
})

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Филиал": st.column_config.TextColumn(width="medium"),
    },
)

# ── Алерты ─────────────────────────────────────────────────────────────

if not alerts.empty:
    st.divider()
    st.subheader("Алерты и предупреждения")

    for _, row in alerts.sort_values("created_at", ascending=False).head(6).iterrows():
        icon = SEVERITY_ICONS.get(row["severity"], "⚪")
        color = SEVERITY_COLORS.get(row["severity"], "#64748b")
        with st.container():
            st.markdown(
                f"""<div style="border-left: 4px solid {color}; padding: 8px 16px;
                margin-bottom: 8px; background: #f8fafc; border-radius: 0 8px 8px 0;">
                <strong>{icon} {row['branch_name']}</strong> — {row['description']}<br>
                <small style="color: #64748b">📌 {row['recommendation']}</small>
                </div>""",
                unsafe_allow_html=True,
            )
