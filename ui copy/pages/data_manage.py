"""البيانات والإعدادات: إعدادات اللقطة، افتراضات المحرك، استيراد بيانات الإيرادات، القوالب، وقاموس البيانات."""
from __future__ import annotations

import io
import zipfile
from datetime import date

import pandas as pd
import streamlit as st

from core.config import ENGINE_DEFAULTS, demo_mode
from core.exports import _Book, csv_bytes, revenue_template_excel
from core.formatting import esc
from core.revenue_data import read_revenue_files, validate_revenue_bundle
from core.schemas import PERF_TABLES, REVENUE_TABLES, SETTINGS_KEYS

from ..components import html, note, section, table
from ..state import flash, reset_revenue, show_flash, ss

KIND_AR = {"str": "نص", "float": "رقم", "int": "عدد صحيح", "bool": "منطقي true/false", "date": "تاريخ YYYY-MM-DD", "month": "شهر YYYY-MM", "label": "synthetic / real"}


def render():
    show_flash()
    t1, t2, t3 = st.tabs(["إعدادات اللقطة وافتراضات التحليل", "استيراد بيانات الإيرادات", "قاموس البيانات"])
    with t1:
        _settings()
    with t2:
        _import()
    with t3:
        _dictionary()


def _settings():
    data = ss.rev_data
    s = data.settings
    counts = {"مصادر الإيرادات": len(data.sources), "الأصول والأراضي": len(data.assets), "العقود": len(data.contracts),
              "الفواتير": len(data.receivables), "المراجع السوقية": len(data.benchmarks)}
    note(f"<b>مجموعة البيانات الحالية:</b> {'تجريبية (synthetic)' if s.data_label == 'synthetic' else 'حقيقية (real)'} — {esc(s.source_note)}<br>"
         + " · ".join(f"{esc(k)}: {v}" for k, v in counts.items()), "info")
    section("إعدادات اللقطة", "تؤثر على الفجوة والمساهمة الممكنة حتى نهاية السنة")
    with st.form("form_rev_settings"):
        c1, c2, c3 = st.columns(3)
        target = c1.number_input("المستهدف السنوي (ريال)", min_value=0.0, value=float(s.annual_target_sar), step=1_000_000.0, format="%.0f")
        snap = c2.date_input("تاريخ اللقطة", value=s.snapshot_date, min_value=date(s.fiscal_year, 1, 1), max_value=date(s.fiscal_year, 12, 31), format="YYYY-MM-DD")
        basis = c3.selectbox("الأساس المالي", ["cash", "accrual"], index=0 if s.financial_basis == "cash" else 1,
                             format_func=lambda b: "نقدي — الإيراد = المحصل فعليًا" if b == "cash" else "استحقاق — الإيراد عند نشوء الحق")
        st.caption("تغيير تاريخ اللقطة يغيّر الأيام المتبقية وأثر مهلة التنفيذ فقط؛ لا يعيد حساب المحقق — حدّث المحقق والمتوقع أصلًا عبر الاستيراد ليتطابقا مع التاريخ الجديد.")
        if st.form_submit_button("تطبيق الإعدادات", type="primary"):
            ss.rev_data = data.with_settings(annual_target_sar=float(target), snapshot_date=snap, financial_basis=basis)
            flash("طُبّقت إعدادات اللقطة على الجلسة الحالية.")
            st.rerun()
    section("افتراضات محرك الفرص", "قيم افتراضية تجريبية تحتاج معايرة ببيانات حقيقية")
    p = ss.engine_params
    with st.form("form_engine_params"):
        c1, c2, c3, c4 = st.columns(4)
        win = c1.number_input("نافذة التجديد (يوم)", 30, 730, int(p["renewal_window_days"]), 15)
        thr = c2.number_input("حد الانخفاض عن المرجع %", 0, 90, int(round(p["underpricing_threshold"] * 100)), 1)
        mod = c3.number_input("الحد الأدنى للتأخير (يوم)", 0, 720, int(p["min_overdue_days"]), 15)
        camp = c4.number_input("مدة حملة التحصيل (يوم)", 15, 720, int(p["collection_campaign_days"]), 15)
        c1, c2, c3, c4 = st.columns(4)
        r1 = c1.number_input("استرداد 90–180 يومًا %", 0, 100, int(round(p["recovery_rates"]["90-180"] * 100)), 5)
        r2 = c2.number_input("استرداد 181–365 يومًا %", 0, 100, int(round(p["recovery_rates"]["181-365"] * 100)), 5)
        r3 = c3.number_input("استرداد أكثر من سنة %", 0, 100, int(round(p["recovery_rates"]["365+"] * 100)), 5)
        rl = c4.number_input("مهلة مراجعة التجديد (يوم)", 0, 365, int(p["renewal_lead_days"]), 5)
        b1, b2 = st.columns([1, 1])
        apply = b1.form_submit_button("تطبيق الافتراضات", type="primary")
        reset = b2.form_submit_button("استعادة القيم الافتراضية")
        if apply:
            ss.engine_params = {**p, "renewal_window_days": int(win), "underpricing_threshold": thr / 100, "min_overdue_days": int(mod),
                                "collection_campaign_days": int(camp), "renewal_lead_days": int(rl),
                                "recovery_rates": {"90-180": r1 / 100, "181-365": r2 / 100, "365+": r3 / 100}}
            flash("طُبّقت الافتراضات وأُعيد استخراج الفرص.")
            st.rerun()
        if reset:
            ss.engine_params = dict(ENGINE_DEFAULTS)
            flash("أُعيدت الافتراضات الافتراضية.")
            st.rerun()
    section("البيانات التجريبية")
    if st.button("استعادة بيانات الإيرادات التجريبية الأصلية", key="rev_reset"):
        reset_revenue()
        flash("أُعيدت بيانات الإيرادات التجريبية والإعدادات الافتراضية. بيانات الأداء لم تتغير.")
        st.rerun()


def _import():
    note("ارفع <b>ملف Excel واحدًا</b> بالأوراق: " + "، ".join(f"«{k}»" for k in REVENUE_TABLES) + "، أو <b>عدة ملفات CSV</b> بنفس الأسماء. "
         "يتم التحقق من الأعمدة والأنواع والمعرفات المكررة والمراجع بين الجداول والتواريخ والقيم السالبة وغير المحدودة والنسب وخلط البيانات الحقيقية والتجريبية. "
         "<b>عند أي خطأ لا تُستبدل أي بيانات</b>، وعند النجاح تُستبدل مجموعة الإيرادات كاملة دون المساس ببيانات الأداء.", "info")
    if demo_mode():
        note("هذه نسخة عرض: تُقبل البيانات الموسومة <b>synthetic</b> فقط. لتحليل بيانات حقيقية يُشغّل النظام داخليًا مع HAIL_DEMO_MODE=0.", "warn")
    c1, c2, c3 = st.columns(3)
    c1.download_button("تنزيل قالب Excel", revenue_template_excel(), "revenue_template.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    c2.download_button("تنزيل قوالب CSV (ZIP)", _csv_templates_zip(), "revenue_csv_templates.zip", "application/zip", width="stretch")
    c3.download_button("تنزيل البيانات الحالية (Excel)", _current_workbook(), "revenue_current_data.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    files = st.file_uploader("ملفات بيانات الإيرادات", type=["xlsx", "csv"], accept_multiple_files=True, key=f"ri_files_{ss.get('ri_ver', 0)}")
    if files and st.button("التحقق من الملفات", type="primary", key="ri_check"):
        try:
            data, rep = validate_revenue_bundle(read_revenue_files(files))
        except Exception as e:  # noqa: BLE001
            data, rep = None, None
            st.error(f"تعذرت قراءة الملفات: {e}")
        if rep is not None and not rep.ok:
            ss.ri_pending = None
            st.error("رُفض الاستيراد ولم تتغير البيانات الحالية. الأخطاء:")
            html("<div class='note bad'><ul>" + "".join(f"<li>{esc(e)}</li>" for e in rep.errors) + "</ul></div>")
        elif data is not None:
            ss.ri_pending = (data, rep.warnings)
    pend = ss.get("ri_pending")
    if pend:
        data, warns = pend
        html(f"<div class='note ok'><b>الملفات صالحة.</b> مصادر {len(data.sources)} · أصول {len(data.assets)} · عقود {len(data.contracts)} · فواتير {len(data.receivables)} · مراجع {len(data.benchmarks)} — "
             f"لقطة {data.settings.snapshot_date.isoformat()}.</div>")
        for w in warns:
            st.warning(w)
        c1, c2 = st.columns(2)
        if c1.button("تأكيد استبدال بيانات الإيرادات", type="primary", key="ri_confirm", width="stretch"):
            reset_revenue(data, source="upload")
            ss.ri_pending = None
            ss.ri_ver = ss.get("ri_ver", 0) + 1
            flash("استُبدلت بيانات الإيرادات بالكامل، وأُعيد استخراج الفرص والاختيار التلقائي.")
            st.rerun()
        if c2.button("إلغاء", key="ri_cancel", width="stretch"):
            ss.ri_pending = None
            st.rerun()


def _csv_templates_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for k, t in REVENUE_TABLES.items():
            if k == "settings":
                df = pd.DataFrame({"key": list(SETTINGS_KEYS), "value": ["2026", "100000000", "2026-09-30", "cash", "synthetic", "وصف المصدر"]})
            else:
                df = pd.DataFrame(columns=t.col_names)
            z.writestr(f"{k}.csv", csv_bytes(df))
    return buf.getvalue()


def _current_workbook() -> bytes:
    b = _Book()
    for k, df in ss.rev_data.tables().items():
        b.table(df, k)
    return b.bytes()


def _dictionary():
    for group, tables in (("بيانات الإيرادات", REVENUE_TABLES), ("بيانات الأداء", PERF_TABLES)):
        section(group)
        for k, t in tables.items():
            with st.expander(f"{t.title} — «{k}»"):
                html(f"<p style='margin:0 0 8px'>{esc(t.desc)}</p>")
                rows = []
                for c in t.columns:
                    cons = []
                    if c.min is not None:
                        cons.append("أكبر من صفر" if 0 < c.min < 1e-3 else f"≥ {c.min:g}")
                    if c.max is not None:
                        cons.append(f"≤ {c.max:g}")
                    if c.choices:
                        cons.append("القيم: " + "، ".join(c.choices))
                    cons.append("يقبل الفراغ" if c.nullable else "مطلوب")
                    if c.name in t.id_cols:
                        cons.append("جزء من المفتاح الفريد")
                    rows.append([f"<b dir='ltr'>{esc(c.name)}</b>", esc(KIND_AR[c.kind]), esc(c.desc), esc(" · ".join(cons))])
                fks = "، ".join(f"{f.col} → {f.table}.{f.ref_col}" for f in t.fks)
                html(table([("العمود", ""), ("النوع", ""), ("الوصف", ""), ("القيود", "")], rows) + (f"<p class='muted' style='margin-top:6px'>المراجع: {esc(fks)}</p>" if fks else ""))
        if group == "بيانات الإيرادات":
            with st.expander("مفاتيح ورقة الإعدادات «settings»"):
                html(table([("المفتاح", ""), ("الوصف", "")], [[f"<b dir='ltr'>{esc(k)}</b>", esc(v)] for k, v in SETTINGS_KEYS.items()]))
