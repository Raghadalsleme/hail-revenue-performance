"""منصة تنمية الإيرادات البلدية ومتابعة أداء الإدارات — نموذج أولي.
Smart Municipal Revenue Growth & Department Performance System (Prototype)

التشغيل:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="منصة تنمية الإيرادات ومتابعة أداء الإدارات — نموذج أولي",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from ui import state, theme  # noqa: E402
from ui.pages import opportunities, performance_dashboard, performance_entry, reports, revenue_dashboard  # noqa: E402

PAGES = [
    {"key": "revenue", "label": "الإيرادات", "title": "الإيرادات", "desc": "المستهدف والمحقق والفجوة.", "render": revenue_dashboard.render},
    {"key": "opportunities", "label": "الفرص", "title": "فرص زيادة الإيرادات", "desc": "اختر الفرص والسيناريو لترى أثرها على الفجوة.", "render": opportunities.render},
    {"key": "performance", "label": "أداء الأقسام", "title": "أداء الأقسام", "desc": "متابعة شهرية لأقسام الإدارة العامة.", "render": performance_dashboard.render},
    {"key": "entry", "label": "إدخال البيانات", "title": "إدخال البيانات", "desc": "إدخال نتائج شهر، تعديل الأقسام، ورفع الملفات.", "render": performance_entry.render},
    {"key": "reports", "label": "التقارير", "title": "التقارير", "desc": "تنزيل التقارير بصيغة PDF وExcel.", "render": reports.render},
]

state.init()
theme.inject_css()
theme.header()
page = theme.nav(PAGES)
theme.page_head(page)
page["render"]()
theme.footer()
