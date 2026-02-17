"""Страница «Cash Flow» — анализ денежного потока."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mock_data import get_data, BRANCHES
from formatters import fmt_rub, BRANCH_COLORS, default_layout

st.header("Cash Flow — Денежный поток")

cf = get_data("cashflow")

# ── Фильтры ───────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("---")
    st.markdown("##### Фильтры CF")
    all_months = sorted(cf["year_month"].unique())
    period = st.select_slider(
        "Период",
        options=all_months,
        value=(all_months[0], all_months[-1]),
        format_func=lambda x: pd.Timestamp(x).strftime("%b %Y"),
        key="cf_period",
    )
    branches_sel = st.multiselect(
        "Филиалы",
        options=list(BRANCHES.values()),
        default=list(BRANCHES.values()),
        key="cf_branches",
    )

mask = (
    (cf["year_month"] >= period[0])
    & (cf["year_month"] <= period[1])
    & (cf["branch_name"].isin(branches_sel))
)
cf = cf[mask]

# ── KPI карточки ───────────────────────────────────────────────────────

inflow = cf[cf["direction"] == "inflow"]["amount"].sum()
outflow = cf[cf["direction"] == "outflow"]["amount"].sum()
net_cf = inflow - outflow

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Приход", fmt_rub(inflow, 1))
with c2:
    st.metric("Расход", fmt_rub(outflow, 1))
with c3:
    st.metric("Чистый CF", fmt_rub(net_cf, 1), f"{net_cf / inflow * 100:+.1f}%" if inflow else None)

st.divider()

# ── Таблица CF по месяцам ──────────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    st.subheader("CF по статьям")

    cf_summary = cf.groupby(["cf_group", "line_item", "direction"]).agg(
        total=("amount", "sum")
    ).reset_index().sort_values(["cf_group", "direction", "total"], ascending=[True, True, False])

    display_rows = []
    for group in cf_summary["cf_group"].unique():
        group_data = cf_summary[cf_summary["cf_group"] == group]
        group_total_in = group_data[group_data["direction"] == "inflow"]["total"].sum()
        group_total_out = group_data[group_data["direction"] == "outflow"]["total"].sum()

        display_rows.append({
            "Статья": f"▸ {group}",
            "Приход": fmt_rub(group_total_in, 1) if group_total_in > 0 else "—",
            "Расход": fmt_rub(group_total_out, 1) if group_total_out > 0 else "—",
            "Нетто": fmt_rub(group_total_in - group_total_out, 1),
        })

        for _, row in group_data.iterrows():
            if row["direction"] == "inflow":
                display_rows.append({
                    "Статья": f"    {row['line_item']}",
                    "Приход": fmt_rub(row["total"], 1),
                    "Расход": "—",
                    "Нетто": fmt_rub(row["total"], 1),
                })
            else:
                display_rows.append({
                    "Статья": f"    {row['line_item']}",
                    "Приход": "—",
                    "Расход": fmt_rub(row["total"], 1),
                    "Нетто": fmt_rub(-row["total"], 1),
                })

    st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True, height=500)

# ── Waterfall приход/расход ────────────────────────────────────────────

with col2:
    st.subheader("Waterfall: приход → расход → нетто")

    top_items = cf.groupby(["line_item", "direction"]).agg(total=("amount", "sum")).reset_index()
    top_items = top_items.sort_values("total", ascending=False)

    inflows = top_items[top_items["direction"] == "inflow"].head(3)
    outflows = top_items[top_items["direction"] == "outflow"].head(8)

    wf_labels = list(inflows["line_item"]) + list(outflows["line_item"]) + ["Чистый CF"]
    wf_values = list(inflows["total"]) + list(-outflows["total"]) + [net_cf]
    wf_measure = ["absolute"] * len(inflows) + ["relative"] * len(outflows) + ["total"]

    fig_wf = go.Figure(go.Waterfall(
        x=wf_labels,
        y=wf_values,
        measure=wf_measure,
        connector={"line": {"color": "#cbd5e1"}},
        increasing={"marker": {"color": "#2563EB"}},
        decreasing={"marker": {"color": "#DC2626"}},
        totals={"marker": {"color": "#059669" if net_cf >= 0 else "#DC2626"}},
        textposition="outside",
        text=[fmt_rub(abs(v), 1) for v in wf_values],
    ))
    fig_wf.update_layout(**default_layout(), height=500, showlegend=False)
    fig_wf.update_xaxes(tickangle=-45)
    st.plotly_chart(fig_wf, use_container_width=True)

st.divider()

# ── Stacked area: структура расходов ───────────────────────────────────

col3, col4 = st.columns(2)

with col3:
    st.subheader("Структура расходов во времени")

    expenses = cf[cf["direction"] == "outflow"].copy()
    exp_monthly = expenses.groupby(["year_month", "line_item"]).agg(
        total=("amount", "sum")
    ).reset_index()

    top_expense_items = expenses.groupby("line_item")["amount"].sum().nlargest(6).index.tolist()
    exp_monthly_top = exp_monthly[exp_monthly["line_item"].isin(top_expense_items)]

    fig_area = px.area(
        exp_monthly_top.sort_values("year_month"),
        x="year_month", y="total", color="line_item",
        labels={"total": "₽", "year_month": "", "line_item": "Статья"},
    )
    fig_area.update_layout(**default_layout(), height=400)
    st.plotly_chart(fig_area, use_container_width=True)

# ── Кумулятивный баланс ───────────────────────────────────────────────

with col4:
    st.subheader("Кумулятивный баланс")

    monthly_net = cf.copy()
    monthly_net["signed_amount"] = monthly_net.apply(
        lambda r: r["amount"] if r["direction"] == "inflow" else -r["amount"], axis=1
    )
    monthly_balance = monthly_net.groupby("year_month")["signed_amount"].sum().cumsum().reset_index()
    monthly_balance.columns = ["year_month", "balance"]

    fig_bal = go.Figure()
    fig_bal.add_trace(go.Scatter(
        x=monthly_balance["year_month"],
        y=monthly_balance["balance"],
        fill="tozeroy",
        fillcolor="rgba(37, 99, 235, 0.1)",
        line=dict(color="#2563EB", width=3),
        name="Баланс",
    ))
    fig_bal.update_layout(**default_layout(), height=400, yaxis_title="₽")
    st.plotly_chart(fig_bal, use_container_width=True)

# ── Топ-5 статей расходов ─────────────────────────────────────────────

st.divider()
st.subheader("Топ статей расходов")

top_exp = expenses.groupby("line_item")["amount"].sum().nlargest(8).reset_index()
top_exp = top_exp.sort_values("amount", ascending=True)

fig_top = go.Figure(go.Bar(
    x=top_exp["amount"],
    y=top_exp["line_item"],
    orientation="h",
    marker_color="#DC2626",
    text=top_exp["amount"].apply(lambda x: fmt_rub(x, 1)),
    textposition="outside",
))
fig_top.update_layout(**default_layout(), height=350, showlegend=False, xaxis_title="₽")
st.plotly_chart(fig_top, use_container_width=True)
