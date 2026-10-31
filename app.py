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
from ui.pages import (data_manage, methodology, opportunities, performance_dashboard, performance_entry, reports,  # noqa: E402
                      revenue_dashboard, scenarios)

PAGES = [
    {"key": "revenue", "label": "لوحة الإيرادات", "group": "تنمية الإيرادات", "title": "لوحة الإيرادات",
     "desc": "المستهدف السنوي والمحقق حتى تاريخ اللقطة والفجوة، والإيرادات حسب المصدر، ومساهمة الفرص المختارة في تقليص الفجوة.", "render": revenue_dashboard.render},
    {"key": "opportunities", "label": "فرص الإيرادات", "group": "تنمية الإيرادات", "title": "محرك اكتشاف فرص الإيرادات",
     "desc": "فرص مستخرجة من بيانات الأصول والعقود والمستحقات بقواعد قابلة للتفسير، لكل فرصة أدلتها وطريقة حسابها وافتراضاتها والموافقات المطلوبة.", "render": opportunities.render},
    {"key": "scenarios", "label": "السيناريوهات", "group": "تنمية الإيرادات", "title": "السيناريوهات واختيار الفرص",
     "desc": "اختر الفرص أو دع النظام يختار الأعلى أولوية، وجرّب السيناريو المتحفظ والمتوسط والمتفائل لرؤية الإيراد الإضافي والفجوة المتبقية أو الفائض.", "render": scenarios.render},
    {"key": "performance", "label": "أداء الإدارات", "group": "متابعة الأداء", "title": "لوحة متابعة أداء الأقسام",
     "desc": "متابعة شهرية لأقسام الإدارة العامة: الدرجة والحالة وسبب التصنيف والتغير عن الشهر السابق والمؤشرات غير المحققة.", "render": performance_dashboard.render},
    {"key": "perf_entry", "label": "إدخال بيانات الأداء", "group": "متابعة الأداء", "title": "إدخال بيانات الأداء وإدارتها",
     "desc": "إدخال أو تعديل شهر، وتعديل أسماء الإدارات والأقسام بمعرفات ثابتة، واستيراد CSV/Excel، والقوالب والنسخ الاحتياطي.", "render": performance_entry.render},
    {"key": "data", "label": "البيانات والإعدادات", "group": "تنمية الإيرادات", "title": "بيانات الإيرادات والإعدادات",
     "desc": "إعدادات اللقطة والأساس المالي، وافتراضات محرك الفرص، واستيراد بيانات الإيرادات مع التحقق، والقوالب وقاموس البيانات.", "render": data_manage.render},
    {"key": "reports", "label": "التقارير", "group": "التقارير", "title": "التقارير والتصدير",
     "desc": "تقرير PDF عربي وملف Excel لفرص الإيرادات والسيناريو المختار، وملخص أداء الشهر والإدارة بصيغتي Excel وPDF.", "render": reports.render},
    {"key": "method", "label": "المنهجية", "group": "عن المنصة", "title": "المنهجية والافتراضات وحدود النموذج",
     "desc": "كيف تُحسب الفجوة والفرص والسيناريوهات ودرجات الأداء، وما الذي يلزم قبل أي استخدام رسمي.", "render": methodology.render},
]

state.init()
theme.inject_css()
theme.header()
page = theme.nav(PAGES)
theme.page_head(page)
page["render"]()
theme.footer()
