"""Страница «P&L» — отчёт о прибылях и убытках."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mock_data import get_data, BRANCHES
from formatters import (
    fmt_rub, fmt_pct, BRANCH_COLORS, default_layout,
)

st.header("P&L — Прибыли и убытки")

pnl = get_data("monthly_pnl")

# ── Фильтры ───────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("---")
    st.markdown("##### Фильтры P&L")

    all_months = sorted(pnl["year_month"].unique())
    period = st.select_slider(
        "Период",
        options=all_months,
        value=(all_months[0], all_months[-1]),
        format_func=lambda x: pd.Timestamp(x).strftime("%b %Y"),
        key="pnl_period",
    )

    branches_sel = st.multiselect(
        "Филиалы",
        options=list(BRANCHES.values()),
        default=list(BRANCHES.values()),
        key="pnl_branches",
    )

mask = (
    (pnl["year_month"] >= period[0])
    & (pnl["year_month"] <= period[1])
    & (pnl["branch_name"].isin(branches_sel))
)
pnl = pnl[mask]

# ── Агрегированная P&L-таблица ─────────────────────────────────────────

st.subheader("Сводная таблица P&L")

monthly_agg = pnl.groupby("year_month").agg({
    "gross_revenue": "sum",
    "refunds": "sum",
    "revenue_accrual": "sum",
    "materials": "sum",
    "lab": "sum",
    "gross_margin": "sum",
    "payroll_doctors": "sum",
    "payroll_assistants": "sum",
    "total_payroll_direct": "sum",
    "rent": "sum",
    "marketing": "sum",
    "it_costs": "sum",
    "ebitda": "sum",
}).reset_index()

monthly_agg["month_label"] = monthly_agg["year_month"].dt.strftime("%b %Y")
monthly_agg["ebitda_margin"] = monthly_agg["ebitda"] / monthly_agg["revenue_accrual"] * 100
monthly_agg["gross_margin_pct"] = monthly_agg["gross_margin"] / monthly_agg["revenue_accrual"] * 100

pnl_lines = [
    ("Выручка (gross)", "gross_revenue"),
    ("  Возвраты", "refunds"),
    ("Выручка (net)", "revenue_accrual"),
    ("", None),
    ("Материалы", "materials"),
    ("Лабораторные", "lab"),
    ("Валовая маржа", "gross_margin"),
    ("", None),
    ("ФОТ врачи", "payroll_doctors"),
    ("ФОТ ассистенты", "payroll_assistants"),
    ("ФОТ итого", "total_payroll_direct"),
    ("", None),
    ("Аренда", "rent"),
    ("Маркетинг", "marketing"),
    ("IT и ПО", "it_costs"),
    ("", None),
    ("EBITDA", "ebitda"),
]

recent_months = monthly_agg.tail(6)

table_data = {"Статья": []}
for _, row in recent_months.iterrows():
    table_data[row["month_label"]] = []

for line_name, col_name in pnl_lines:
    table_data["Статья"].append(line_name)
    for _, row in recent_months.iterrows():
        if col_name is None:
            table_data[row["month_label"]].append("")
        else:
            table_data[row["month_label"]].append(fmt_rub(row[col_name], 1))

# Total column
table_data["Итого"] = []
for line_name, col_name in pnl_lines:
    if col_name is None:
        table_data["Итого"].append("")
    else:
        table_data["Итого"].append(fmt_rub(monthly_agg[col_name].sum(), 1))

pnl_df = pd.DataFrame(table_data)
st.dataframe(pnl_df, use_container_width=True, hide_index=True, height=600)

st.divider()

# ── Waterfall: от выручки до EBITDA ────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    st.subheader("Декомпозиция выручка → EBITDA")

    totals = pnl.agg({
        "revenue_accrual": "sum",
        "materials": "sum",
        "lab": "sum",
        "payroll_doctors": "sum",
        "payroll_assistants": "sum",
        "rent": "sum",
        "marketing": "sum",
        "it_costs": "sum",
        "ebitda": "sum",
    })

    wf_labels = [
        "Выручка", "Материалы", "Лаборатория",
        "ФОТ врачи", "ФОТ ассист.", "Аренда",
        "Маркетинг", "IT", "EBITDA",
    ]
    wf_values = [
        totals["revenue_accrual"],
        -totals["materials"],
        -totals["lab"],
        -totals["payroll_doctors"],
        -totals["payroll_assistants"],
        -totals["rent"],
        -totals["marketing"],
        -totals["it_costs"],
        totals["ebitda"],
    ]
    wf_measure = ["absolute"] + ["relative"] * 7 + ["total"]

    fig_wf = go.Figure(go.Waterfall(
        x=wf_labels,
        y=wf_values,
        measure=wf_measure,
        connector={"line": {"color": "#cbd5e1"}},
        increasing={"marker": {"color": "#2563EB"}},
        decreasing={"marker": {"color": "#DC2626"}},
        totals={"marker": {"color": "#059669"}},
        textposition="outside",
        text=[fmt_rub(abs(v), 1) for v in wf_values],
    ))
    fig_wf.update_layout(**default_layout(), height=450, showlegend=False)
    st.plotly_chart(fig_wf, use_container_width=True)

# ── Динамика статей расходов ───────────────────────────────────────────

with col2:
    st.subheader("Динамика расходов")

    expense_cols = {
        "Материалы": "materials",
        "Лаборатория": "lab",
        "ФОТ врачи": "payroll_doctors",
        "ФОТ ассистенты": "payroll_assistants",
        "Аренда": "rent",
        "Маркетинг": "marketing",
    }

    fig_exp = go.Figure()
    colors = ["#DC2626", "#D97706", "#2563EB", "#7C3AED", "#059669", "#0891B2"]
    for i, (label, col) in enumerate(expense_cols.items()):
        fig_exp.add_trace(go.Scatter(
            x=monthly_agg["year_month"],
            y=monthly_agg[col],
            name=label,
            line=dict(width=2, color=colors[i]),
        ))
    fig_exp.update_layout(**default_layout(), height=450, yaxis_title="₽")
    st.plotly_chart(fig_exp, use_container_width=True)

st.divider()

# ── YoY-сравнение ─────────────────────────────────────────────────────

st.subheader("Год к году (YoY)")

pnl_full = get_data("monthly_pnl")
pnl_full = pnl_full[pnl_full["branch_name"].isin(branches_sel)]

y2024 = pnl_full[pnl_full["year_month"].dt.year == 2024].agg({
    "revenue_accrual": "sum", "ebitda": "sum",
    "materials": "sum", "total_payroll_direct": "sum",
    "unique_patients": "sum", "avg_ticket": "mean",
})
y2025 = pnl_full[pnl_full["year_month"].dt.year == 2025].agg({
    "revenue_accrual": "sum", "ebitda": "sum",
    "materials": "sum", "total_payroll_direct": "sum",
    "unique_patients": "sum", "avg_ticket": "mean",
})

yoy_rows = []
for metric, label in [
    ("revenue_accrual", "Выручка"),
    ("ebitda", "EBITDA"),
    ("materials", "Материалы"),
    ("total_payroll_direct", "ФОТ"),
    ("unique_patients", "Пациенты"),
    ("avg_ticket", "Средний чек"),
]:
    v24 = y2024[metric]
    v25 = y2025[metric]
    delta = (v25 / v24 - 1) * 100 if v24 else 0
    if metric in ("unique_patients",):
        yoy_rows.append({
            "Показатель": label,
            "2024": fmt_rub(v24) if metric != "unique_patients" else f"{int(v24):,}".replace(",", " "),
            "2025": fmt_rub(v25) if metric != "unique_patients" else f"{int(v25):,}".replace(",", " "),
            "Δ%": fmt_pct(delta),
        })
    else:
        yoy_rows.append({
            "Показатель": label,
            "2024": fmt_rub(v24, 1),
            "2025": fmt_rub(v25, 1),
            "Δ%": fmt_pct(delta),
        })

yoy_df = pd.DataFrame(yoy_rows)
st.dataframe(yoy_df, use_container_width=True, hide_index=True)

# ── P&L по филиалам ───────────────────────────────────────────────────

st.divider()
st.subheader("EBITDA-маржа по филиалам")

branch_ebitda = pnl.groupby("branch_name").agg({
    "revenue_accrual": "sum",
    "ebitda": "sum",
}).reset_index()
branch_ebitda["ebitda_margin"] = branch_ebitda["ebitda"] / branch_ebitda["revenue_accrual"] * 100
branch_ebitda = branch_ebitda.sort_values("ebitda_margin", ascending=True)

fig_margin = go.Figure(go.Bar(
    x=branch_ebitda["ebitda_margin"],
    y=branch_ebitda["branch_name"],
    orientation="h",
    marker_color=[BRANCH_COLORS.get(b, "#94a3b8") for b in branch_ebitda["branch_name"]],
    text=branch_ebitda["ebitda_margin"].apply(lambda x: f"{x:.1f}%"),
    textposition="outside",
))
fig_margin.update_layout(
    **default_layout(),
    height=350,
    xaxis_title="EBITDA маржа, %",
    showlegend=False,
)
st.plotly_chart(fig_margin, use_container_width=True)
