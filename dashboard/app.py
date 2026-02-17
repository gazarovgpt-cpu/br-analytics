"""Управленческий дашборд «Белая Радуга» — точка входа."""

import streamlit as st

st.set_page_config(
    page_title="Белая Радуга — Аналитика",
    page_icon="🦷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* KPI-карточки */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    div[data-testid="stMetric"] label {
        font-size: 0.85rem !important;
        color: #64748b !important;
        font-weight: 500 !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        color: #1e293b !important;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #f1f5f9 !important;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stMultiSelect label,
    section[data-testid="stSidebar"] .stDateInput label {
        color: #cbd5e1 !important;
    }

    /* Таблицы */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }

    /* Разделитель */
    hr {
        border-color: #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)

# ── Навигация ──────────────────────────────────────────────────────────

overview_page = st.Page("pages/1_overview.py", title="Обзор", icon="📊", default=True)
pnl_page = st.Page("pages/2_pnl.py", title="P&L", icon="📋")
cashflow_page = st.Page("pages/3_cashflow.py", title="Cash Flow", icon="💰")
doctors_page = st.Page("pages/4_doctors.py", title="KPI врачей", icon="👨‍⚕️")
branches_page = st.Page("pages/5_branches.py", title="Филиалы", icon="🏥")
services_page = st.Page("pages/6_services.py", title="Услуги", icon="🔬")
planning_page = st.Page("pages/7_planning.py", title="Планирование", icon="📈")

pg = st.navigation([
    overview_page, pnl_page, cashflow_page,
    doctors_page, branches_page, services_page,
    planning_page,
])

# ── Sidebar ────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🦷 Белая Радуга")
    st.caption("Управленческая аналитика")
    st.divider()

    st.markdown("##### Демо-режим")
    st.info("Данные сгенерированы для демонстрации интерфейса", icon="ℹ️")

pg.run()
