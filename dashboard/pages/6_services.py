"""Страница «Услуги» — экономика и маржинальность."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mock_data import get_data, BRANCHES
from formatters import fmt_rub, fmt_pct, fmt_num, BRANCH_COLORS, default_layout

st.header("Экономика услуг")

svc = get_data("service_economics")

# ── Фильтры ───────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("---")
    st.markdown("##### Фильтры услуг")

    branches_sel = st.multiselect(
        "Филиалы",
        options=list(BRANCHES.values()),
        default=list(BRANCHES.values()),
        key="svc_branches",
    )

    categories = sorted(svc["category"].unique())
    cats_sel = st.multiselect(
        "Категории",
        options=categories,
        default=categories,
        key="svc_cats",
    )

svc = svc[(svc["branch_name"].isin(branches_sel)) & (svc["category"].isin(cats_sel))]

# ── KPI карточки ───────────────────────────────────────────────────────

total_rev = svc["total_revenue"].sum()
avg_margin = svc["margin_pct"].mean()
total_services = svc["service_count"].sum()
unique_services = svc["service_name"].nunique()

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Выручка от услуг", fmt_rub(total_rev, 1))
with c2:
    st.metric("Средняя маржа", fmt_pct(avg_margin))
with c3:
    st.metric("Всего оказано", fmt_num(total_services))
with c4:
    st.metric("Видов услуг", fmt_num(unique_services))

st.divider()

# ── Treemap выручки ────────────────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    st.subheader("Структура выручки по категориям")

    tree_data = svc.groupby(["category", "service_name"]).agg({
        "total_revenue": "sum",
    }).reset_index()

    fig_tree = px.treemap(
        tree_data,
        path=["category", "service_name"],
        values="total_revenue",
        color="total_revenue",
        color_continuous_scale="Blues",
    )
    fig_tree.update_layout(**default_layout(), height=450)
    fig_tree.update_traces(textinfo="label+value+percent root")
    st.plotly_chart(fig_tree, use_container_width=True)

# ── Scatter: маржа vs объём ────────────────────────────────────────────

with col2:
    st.subheader("Маржа vs Объём (поиск дефицитов)")

    svc_agg = svc.groupby(["service_name", "category"]).agg({
        "total_revenue": "sum",
        "service_count": "sum",
        "margin_pct": "mean",
        "avg_price": "mean",
    }).reset_index()

    fig_scatter = px.scatter(
        svc_agg,
        x="total_revenue",
        y="margin_pct",
        size="service_count",
        color="category",
        hover_name="service_name",
        labels={
            "total_revenue": "Выручка, ₽",
            "margin_pct": "Маржа, %",
            "service_count": "Кол-во",
            "category": "Категория",
        },
        size_max=35,
    )

    fig_scatter.add_hline(y=50, line_dash="dash", line_color="#DC2626", opacity=0.5,
                          annotation_text="Целевая маржа 50%")

    fig_scatter.update_layout(**default_layout(), height=450)
    st.plotly_chart(fig_scatter, use_container_width=True)

st.divider()

# ── Таблица маржинальности ─────────────────────────────────────────────

st.subheader("Таблица маржинальности услуг")

table_data = svc_agg.sort_values("total_revenue", ascending=False).copy()

display_df = pd.DataFrame({
    "Услуга": table_data["service_name"],
    "Категория": table_data["category"],
    "Кол-во": table_data["service_count"],
    "Выручка": table_data["total_revenue"],
    "Ср. цена": table_data["avg_price"].round(0),
    "Маржа %": table_data["margin_pct"].round(1),
})

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Выручка": st.column_config.NumberColumn(format="%.0f ₽"),
        "Ср. цена": st.column_config.NumberColumn(format="%.0f ₽"),
        "Маржа %": st.column_config.ProgressColumn(
            min_value=0,
            max_value=100,
            format="%.1f%%",
        ),
    },
    height=500,
)

st.divider()

# ── Топ-10 по выручке и маржинальности ────────────────────────────────

col3, col4 = st.columns(2)

with col3:
    st.subheader("Топ-10 по выручке")

    top_rev = svc_agg.nlargest(10, "total_revenue").sort_values("total_revenue", ascending=True)
    fig_top_rev = go.Figure(go.Bar(
        x=top_rev["total_revenue"],
        y=top_rev["service_name"],
        orientation="h",
        marker_color="#2563EB",
        text=top_rev["total_revenue"].apply(lambda x: fmt_rub(x, 1)),
        textposition="outside",
    ))
    fig_top_rev.update_layout(**default_layout(), height=400, showlegend=False, xaxis_title="₽")
    st.plotly_chart(fig_top_rev, use_container_width=True)

with col4:
    st.subheader("Топ-10 по маржинальности")

    top_margin = svc_agg.nlargest(10, "margin_pct").sort_values("margin_pct", ascending=True)
    fig_top_m = go.Figure(go.Bar(
        x=top_margin["margin_pct"],
        y=top_margin["service_name"],
        orientation="h",
        marker_color="#059669",
        text=top_margin["margin_pct"].apply(lambda x: f"{x:.1f}%"),
        textposition="outside",
    ))
    fig_top_m.update_layout(**default_layout(), height=400, showlegend=False, xaxis_title="Маржа, %")
    st.plotly_chart(fig_top_m, use_container_width=True)

# ── Выручка по категориям и филиалам ───────────────────────────────────

st.divider()
st.subheader("Выручка по категориям и филиалам")

cat_branch = svc.groupby(["category", "branch_name"])["total_revenue"].sum().reset_index()
fig_cat = px.bar(
    cat_branch,
    x="category", y="total_revenue",
    color="branch_name",
    color_discrete_map=BRANCH_COLORS,
    barmode="group",
    labels={"total_revenue": "Выручка, ₽", "category": "Категория", "branch_name": "Филиал"},
)
fig_cat.update_layout(**default_layout(), height=400)
st.plotly_chart(fig_cat, use_container_width=True)
