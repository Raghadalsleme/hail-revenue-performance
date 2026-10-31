"""الهيكل العام: CSS، الترويسة، شريط التنقل الأفقي، رأس الصفحة، التذييل."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.config import APP_NAME_AR, APP_NAME_EN, APP_VERSION, ORG_NAME_AR, ORG_NAME_EN, PROTOTYPE_NOTICE, SYNTHETIC_NOTICE, demo_mode  # noqa: F401
from core.formatting import date_ar, esc

from .components import html, logo_data_uri
from .state import ss, storage_label

CSS = (Path(__file__).parent / "style.css").read_text(encoding="utf-8")


def inject_css():
    st.html(f"<style>{CSS}</style>")


def header():
    s = ss.rev_data.settings
    logo = logo_data_uri()
    if logo:
        brand = f'<img class="gov-logo" src="{logo}" alt="شعار {ORG_NAME_AR}">'
    else:
        # لا يُرسم شعار بديل: يُعرض اسم الجهة نصًا حتى يُضاف ملف الشعار الرسمي في assets/logo
        brand = f'<div class="gov-wordmark"><b>{ORG_NAME_AR}</b><span>{ORG_NAME_EN}</span></div>'
    html(f"""
<header class="gov-header full-bleed">
  <div class="gov-brand">{brand}<div class="gov-sep"></div>
    <div class="gov-title"><h1>{APP_NAME_AR}</h1><p>{APP_NAME_EN}</p></div>
  </div>
  <div class="gov-meta">
    <span>بيانات الإيرادات حتى {date_ar(s.snapshot_date)}</span>
    <span>حفظ بيانات الأداء: {esc(storage_label())}</span>
  </div>
</header>""")


def nav(pages: list[dict]) -> dict:
    """شريط تنقل أفقي (راديو بتصميم تبويبات) متزامن مع ?page= في الرابط."""
    keys = [p["key"] for p in pages]
    if "nav" not in ss:
        qp = st.query_params.get("page")
        ss.nav = qp if qp in keys else keys[0]
    labels = {p["key"]: p["label"] for p in pages}
    with st.container(key="topnav"):
        st.radio("التنقل بين صفحات المنصة", keys, format_func=lambda k: labels[k], horizontal=True, key="nav", label_visibility="collapsed")
    if st.query_params.get("page") != ss.nav:
        st.query_params["page"] = ss.nav
    # على الشاشات الضيقة: إظهار التبويب النشط داخل شريط التنقل القابل للتمرير
    st.html("""<script>(function(){const t=()=>{const el=document.querySelector('.st-key-topnav [data-selected="true"]');
if(el&&el.parentElement){el.scrollIntoView({block:'nearest',inline:'center'});}};setTimeout(t,150);setTimeout(t,800);})();</script>""",
            unsafe_allow_javascript=True)
    return next(p for p in pages if p["key"] == ss.nav)


def page_head(page: dict):
    html(f"""<div class="page-head"><div class="crumb"><span>المنصة</span><span class="sep">/</span><span>{esc(page['group'])}</span>
<span class="sep">/</span><b>{esc(page['label'])}</b></div><h2>{esc(page['title'])}</h2><p>{esc(page['desc'])}</p></div>""")


def footer():
    """حالة النظام تُعرض في آخر الصفحة بدل الشريط العلوي (بناءً على طلب المستخدم)، دون حذفها."""
    mode = "وضع العرض: تُقبل البيانات التجريبية فقط" if demo_mode() else "وضع داخلي: يقبل بيانات موسومة كحقيقية"
    html(f"""<div class="gov-footer">
  <div class="gov-footer-notes">
    <span><b>{PROTOTYPE_NOTICE}</b> — الإصدار {APP_VERSION}</span>
    <span>{SYNTHETIC_NOTICE}</span>
    <span>لا يوجد نموذج تعلم آلة مدرب في هذا الإصدار؛ النتائج مبنية على قواعد تحليلية قابلة للتفسير وافتراضات موضحة في صفحة «المنهجية».</span>
  </div>
  <div class="gov-footer-meta"><span>{APP_NAME_AR}</span><span>{mode}</span></div>
</div>""")
