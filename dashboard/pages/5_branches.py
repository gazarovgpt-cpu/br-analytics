"""Страница «Филиалы» — сравнение и ранжирование."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mock_data import get_data, BRANCHES
from formatters import fmt_rub, fmt_num, fmt_pct, BRANCH_COLORS, default_layout

st.header("Сравнение филиалов")

pnl = get_data("monthly_pnl")
bc = get_data("branch_comparison")

# ── Фильтры ───────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("---")
    st.markdown("##### Фильтры филиалов")
    all_months = sorted(pnl["year_month"].unique())
    period = st.select_slider(
        "Период",
        options=all_months,
        value=(all_months[0], all_months[-1]),
        format_func=lambda x: pd.Timestamp(x).strftime("%b %Y"),
        key="br_period",
    )

mask = (pnl["year_month"] >= period[0]) & (pnl["year_month"] <= period[1])
pnl = pnl[mask]
bc_mask = (bc["year_month"] >= period[0]) & (bc["year_month"] <= period[1])
bc = bc[bc_mask]

# ── Radar chart ────────────────────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    st.subheader("Многомерное сравнение")

    branch_agg = pnl.groupby("branch_name").agg({
        "revenue_accrual": "sum",
        "ebitda": "sum",
        "unique_patients": "sum",
        "avg_ticket": "mean",
        "primary_visits": "sum",
    }).reset_index()

    metrics = ["revenue_accrual", "ebitda", "unique_patients", "avg_ticket", "primary_visits"]
    labels = ["Выручка", "EBITDA", "Пациенты", "Средний чек", "Первичные"]

    normalized = branch_agg.copy()
    for m in metrics:
        max_val = normalized[m].max()
        if max_val > 0:
            normalized[m] = normalized[m] / max_val * 100

    fig_radar = go.Figure()
    for _, row in normalized.iterrows():
        values = [row[m] for m in metrics] + [row[metrics[0]]]
        fig_radar.add_trace(go.Scatterpolar(
            r=values,
            theta=labels + [labels[0]],
            name=row["branch_name"],
            line=dict(color=BRANCH_COLORS.get(row["branch_name"], "#94a3b8"), width=2),
            fill="toself",
            fillcolor=BRANCH_COLORS.get(row["branch_name"], "#94a3b8").replace(")", ", 0.05)").replace("rgb", "rgba") if "rgb" in BRANCH_COLORS.get(row["branch_name"], "") else None,
            opacity=0.8,
        ))
    fig_radar.update_layout(
        **default_layout(),
        height=450,
        polar=dict(radialaxis=dict(visible=True, range=[0, 110])),
    )
    st.plotly_chart(fig_radar, use_container_width=True)

# ── Доля в выручке (Donut) ────────────────────────────────────────────

with col2:
    st.subheader("Доля филиалов в выручке")

    rev_by_branch = pnl.groupby("branch_name")["revenue_accrual"].sum().reset_index()
    rev_by_branch = rev_by_branch.sort_values("revenue_accrual", ascending=False)

    fig_donut = go.Figure(go.Pie(
        labels=rev_by_branch["branch_name"],
        values=rev_by_branch["revenue_accrual"],
        hole=0.45,
        marker=dict(colors=[BRANCH_COLORS.get(b, "#94a3b8") for b in rev_by_branch["branch_name"]]),
        textinfo="label+percent",
        textposition="outside",
    ))
    fig_donut.update_layout(**default_layout(), height=450, showlegend=False)
    st.plotly_chart(fig_donut, use_container_width=True)

st.divider()

# ── Grouped bar: выручка по месяцам ────────────────────────────────────

st.subheader("Выручка по филиалам помесячно")

fig_bars = px.bar(
    pnl.sort_values("year_month"),
    x="year_month", y="revenue_accrual",
    color="branch_name",
    color_discrete_map=BRANCH_COLORS,
    barmode="group",
    labels={"revenue_accrual": "Выручка, ₽", "year_month": "", "branch_name": "Филиал"},
)
fig_bars.update_layout(**default_layout(), height=400)
st.plotly_chart(fig_bars, use_container_width=True)

st.divider()

# ── Таблица ранжирования ──────────────────────────────────────────────

st.subheader("Ранжирование филиалов")

rank_data = branch_agg.copy()
rank_data["ebitda_margin"] = rank_data["ebitda"] / rank_data["revenue_accrual"] * 100
rank_data = rank_data.sort_values("revenue_accrual", ascending=False)

rank_display = pd.DataFrame({
    "# ": range(1, len(rank_data) + 1),
    "Филиал": rank_data["branch_name"].values,
    "Выручка": rank_data["revenue_accrual"].apply(lambda x: fmt_rub(x, 1)).values,
    "EBITDA": rank_data["ebitda"].apply(lambda x: fmt_rub(x, 1)).values,
    "EBITDA маржа": rank_data["ebitda_margin"].apply(lambda x: fmt_pct(x)).values,
    "Пациенты": rank_data["unique_patients"].apply(lambda x: fmt_num(x)).values,
    "Ср. чек": rank_data["avg_ticket"].apply(lambda x: fmt_rub(x)).values,
    "Первичные": rank_data["primary_visits"].apply(lambda x: fmt_num(x)).values,
})

st.dataframe(rank_display, use_container_width=True, hide_index=True)

st.divider()

# ── Детский vs взрослый приём ──────────────────────────────────────────

st.subheader("Детский vs Взрослый приём")

child_agg = bc.groupby("branch_name").agg({
    "children_revenue": "sum",
    "adult_revenue": "sum",
}).reset_index()

fig_child = go.Figure()
fig_child.add_trace(go.Bar(
    x=child_agg["branch_name"],
    y=child_agg["adult_revenue"],
    name="Взрослые",
    marker_color="#2563EB",
))
fig_child.add_trace(go.Bar(
    x=child_agg["branch_name"],
    y=child_agg["children_revenue"],
    name="Дети",
    marker_color="#F59E0B",
))
fig_child.update_layout(**default_layout(), height=380, barmode="stack")
st.plotly_chart(fig_child, use_container_width=True)

# ── Динамика среднего чека ─────────────────────────────────────────────

st.divider()
st.subheader("Динамика среднего чека по филиалам")

fig_ticket = go.Figure()
for bname in BRANCHES.values():
    bdata = pnl[pnl["branch_name"] == bname].sort_values("year_month")
    fig_ticket.add_trace(go.Scatter(
        x=bdata["year_month"],
        y=bdata["avg_ticket"],
        name=bname,
        line=dict(color=BRANCH_COLORS.get(bname, "#94a3b8"), width=2),
    ))
fig_ticket.update_layout(**default_layout(), height=380, yaxis_title="₽")
st.plotly_chart(fig_ticket, use_container_width=True)
