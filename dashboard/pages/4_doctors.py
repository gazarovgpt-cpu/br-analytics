"""Страница «KPI врачей» — производительность и загрузка."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mock_data import get_data, BRANCHES, SPECIALIZATIONS
from formatters import fmt_rub, fmt_num, BRANCH_COLORS, default_layout

st.header("KPI врачей")

docs = get_data("doctor_kpi")

# ── Фильтры ───────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("---")
    st.markdown("##### Фильтры врачей")

    all_months = sorted(docs["year_month"].unique())
    period = st.select_slider(
        "Период",
        options=all_months,
        value=(all_months[0], all_months[-1]),
        format_func=lambda x: pd.Timestamp(x).strftime("%b %Y"),
        key="doc_period",
    )

    branches_sel = st.multiselect(
        "Филиалы",
        options=list(BRANCHES.values()),
        default=list(BRANCHES.values()),
        key="doc_branches",
    )

    specs_sel = st.multiselect(
        "Специализация",
        options=SPECIALIZATIONS,
        default=SPECIALIZATIONS,
        key="doc_specs",
    )

mask = (
    (docs["year_month"] >= period[0])
    & (docs["year_month"] <= period[1])
    & (docs["branch_name"].isin(branches_sel))
    & (docs["specialization"].isin(specs_sel))
)
docs = docs[mask]

# ── Сводная таблица ────────────────────────────────────────────────────

st.subheader("Сводная таблица врачей")

doc_agg = docs.groupby(["doctor_name", "specialization", "branch_name"]).agg({
    "revenue": "sum",
    "visit_count": "sum",
    "unique_patients": "sum",
    "primary_visits": "sum",
    "avg_ticket": "mean",
    "revenue_per_workday": "mean",
}).reset_index().sort_values("revenue", ascending=False)

display_df = pd.DataFrame({
    "Врач": doc_agg["doctor_name"],
    "Специализация": doc_agg["specialization"],
    "Филиал": doc_agg["branch_name"],
    "Выручка": doc_agg["revenue"],
    "Визиты": doc_agg["visit_count"],
    "Пациенты": doc_agg["unique_patients"],
    "Первичные": doc_agg["primary_visits"],
    "Ср. чек": doc_agg["avg_ticket"].round(0),
    "Выручка/день": doc_agg["revenue_per_workday"].round(0),
})

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Выручка": st.column_config.NumberColumn(format="%.0f ₽"),
        "Ср. чек": st.column_config.NumberColumn(format="%.0f ₽"),
        "Выручка/день": st.column_config.NumberColumn(format="%.0f ₽"),
    },
    height=450,
)

st.divider()

# ── Scatter: выручка vs визиты ─────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    st.subheader("Выручка vs Визиты")

    fig_scatter = px.scatter(
        doc_agg,
        x="visit_count",
        y="revenue",
        size="avg_ticket",
        color="branch_name",
        color_discrete_map=BRANCH_COLORS,
        hover_name="doctor_name",
        labels={
            "visit_count": "Кол-во визитов",
            "revenue": "Выручка, ₽",
            "avg_ticket": "Ср. чек",
            "branch_name": "Филиал",
        },
        size_max=30,
    )
    fig_scatter.update_layout(**default_layout(), height=450)
    st.plotly_chart(fig_scatter, use_container_width=True)

# ── Рейтинг врачей по выручке ─────────────────────────────────────────

with col2:
    st.subheader("Топ-15 врачей по выручке")

    top15 = doc_agg.head(15).sort_values("revenue", ascending=True)

    fig_bar = go.Figure(go.Bar(
        x=top15["revenue"],
        y=top15["doctor_name"],
        orientation="h",
        marker_color=[BRANCH_COLORS.get(b, "#94a3b8") for b in top15["branch_name"]],
        text=top15["revenue"].apply(lambda x: fmt_rub(x, 1)),
        textposition="outside",
    ))
    fig_bar.update_layout(**default_layout(), height=450, showlegend=False, xaxis_title="Выручка, ₽")
    st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ── Heatmap загрузки врачей ────────────────────────────────────────────

st.subheader("Загрузка врачей по месяцам (выручка)")

top_doctors = doc_agg.head(15)["doctor_name"].tolist()
heat_data = docs[docs["doctor_name"].isin(top_doctors)].copy()
heat_data["month_label"] = heat_data["year_month"].dt.strftime("%b %y")

heat_pivot = heat_data.pivot_table(
    values="revenue",
    index="doctor_name",
    columns="month_label",
    aggfunc="sum",
    fill_value=0,
)

month_order = heat_data.sort_values("year_month")["month_label"].unique()
heat_pivot = heat_pivot.reindex(columns=month_order)

fig_heat = go.Figure(data=go.Heatmap(
    z=heat_pivot.values,
    x=heat_pivot.columns.tolist(),
    y=heat_pivot.index.tolist(),
    colorscale="Blues",
    hovertemplate="Врач: %{y}<br>Месяц: %{x}<br>Выручка: %{z:,.0f} ₽<extra></extra>",
))
fig_heat.update_layout(
    **default_layout(),
    height=500,
    yaxis=dict(autorange="reversed"),
)
st.plotly_chart(fig_heat, use_container_width=True)

# ── Средний чек по специализациям ──────────────────────────────────────

st.divider()
st.subheader("Средний чек по специализациям")

spec_agg = docs.groupby("specialization").agg({
    "avg_ticket": "mean",
    "revenue": "sum",
    "visit_count": "sum",
}).reset_index().sort_values("avg_ticket", ascending=True)

fig_spec = go.Figure(go.Bar(
    x=spec_agg["avg_ticket"],
    y=spec_agg["specialization"],
    orientation="h",
    marker_color="#7C3AED",
    text=spec_agg["avg_ticket"].apply(lambda x: fmt_rub(x)),
    textposition="outside",
))
fig_spec.update_layout(**default_layout(), height=350, showlegend=False, xaxis_title="Средний чек, ₽")
st.plotly_chart(fig_spec, use_container_width=True)
