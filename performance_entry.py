"""إدخال بيانات الأداء وحفظها: إدخال/تعديل شهر، الإدارات والأقسام، الاستيراد، القوالب والنسخ الاحتياطي."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core.exports import csv_bytes, perf_backup_excel, perf_template_excel
from core.formatting import AR_MONTHS, esc, month_label
from core.performance import (add_dept, add_gd, merge_records_upload, month_wide, read_perf_files, rename_gd, update_depts,
                              upsert_month, validate_perf_bundle)
from core.schemas import PERF_RECORDS

from ..components import html, note, section, table
from ..state import _synthetic_perf, flash, set_perf, show_flash, ss, storage_label


def render():
    show_flash()
    note(f"<b>طريقة الحفظ الحالية:</b> {esc(storage_label())}. "
         + ("البيانات تبقى ما دامت الجلسة مفتوحة وتُفقد عند إغلاق الصفحة أو إعادة تشغيل الخادم؛ استخدم «تنزيل نسخة احتياطية» ثم «استعادة» لاحقًا. "
            if "SQLite" not in storage_label() else "يُحفظ كل تعديل في ملف SQLite محلي على الجهاز الذي يشغّل النظام. ")
         + "بيانات الأداء منفصلة عن بيانات الإيرادات؛ رفع إحداهما لا يمس الأخرى.", "warn")
    t1, t2, t3, t4 = st.tabs(["إدخال أو تعديل شهر", "الإدارات والأقسام", "استيراد ملف CSV أو Excel", "القوالب والنسخ الاحتياطي"])
    with t1:
        _month_entry()
    with t2:
        _structure()
    with t3:
        _import()
    with t4:
        _templates()


def _month_entry():
    perf = ss.perf
    gds = perf.gds[perf.gds["active"].astype(bool)]
    names = dict(zip(gds["gd_id"], gds["gd_name"]))
    c1, c2, c3 = st.columns([1.4, 1, 1])
    gd = c1.selectbox("الإدارة العامة", list(names), format_func=lambda g: names[g], key="pe_gd")
    today = date.today()
    year = c2.selectbox("السنة", list(range(today.year - 3, today.year + 2)), index=3, key="pe_year")
    mon = c3.selectbox("الشهر", list(range(1, 13)), index=max(0, today.month - 2), format_func=lambda m: AR_MONTHS[m - 1], key="pe_mon")
    month = f"{year}-{mon:02d}"
    wide = month_wide(perf, gd, month)
    if wide.empty:
        note("لا توجد أقسام فعالة في هذه الإدارة العامة. أضف أقسامًا من تبويب «الإدارات والأقسام».", "warn")
        return
    exists = perf.records[(perf.records["month"] == month) & perf.records["dept_id"].isin(wide["dept_id"])]
    note(("<b>تعديل شهر سابق:</b> توجد بيانات محفوظة لهذا الشهر وسيستبدل الحفظ قيم أقسام هذه الإدارة فقط." if len(exists)
          else "<b>شهر جديد:</b> لا توجد بيانات لهذا الشهر بعد.") + " اترك الخلية فارغة إذا لم تتوفر القيمة — الفراغ يعني «غير مدخل» ولا يُحتسب صفرًا. القيم من 0 إلى 100.", "info")
    # نموذج إدخال بحقول رقمية (يدعم RTL بالكامل): الحقل الفارغ = «غير مدخل» ولا يتحول إلى صفر
    ver = ss.get("pe_ver", 0)
    with st.form(f"form_month_{gd}_{month}_{ver}"):
        values = []
        for d in wide.itertuples(index=False):
            dd = d._asdict()
            with st.container(key=f"card_entry_{d.dept_id}"):
                html(f'<div class="card-title">{esc(d.dept_name)} <span class="muted" style="font-weight:400;font-size:12px">· {esc(d.dept_id)}</span></div>')
                cols = st.columns(len(perf.kpis) * 2)
                row = {"dept_id": d.dept_id}
                i = 0
                for r in perf.kpis.itertuples():
                    for part, lbl in (("target", "المستهدف"), ("actual", "المحقق")):
                        cur = dd[f"{r.kpi_id}_{part}"]
                        row[f"{r.kpi_id}_{part}"] = cols[i].number_input(
                            f"{r.kpi_name} — {lbl}", min_value=0.0, max_value=100.0, step=0.5, format="%.1f",
                            value=None if cur != cur else float(cur), placeholder="غير مدخل",
                            key=f"pe_{gd}_{month}_{ver}_{d.dept_id}_{r.kpi_id}_{part}",
                            help=(r.definition if part == "target" else "اتركه فارغًا إذا لم يُدخل — لا يُعامل كصفر"))
                        i += 1
                values.append(row)
        c1, c2 = st.columns([1, 3])
        submitted = c1.form_submit_button("حفظ بيانات الشهر", type="primary", width="stretch")
        c2.caption("الحفظ يتحقق من الحدود ويرفض المستهدف الصفري، ثم يستبدل صفوف هذه الأقسام لهذا الشهر فقط دون المساس بالأشهر الأخرى.")
    if submitted:
        edited = pd.DataFrame(values).astype({c: float for c in pd.DataFrame(values).columns if c != "dept_id"})
        new, errs = upsert_month(perf, month, edited)
        if errs:
            for e in errs:
                st.error(e)
        else:
            set_perf(new)
            ss.pe_ver = ver + 1
            flash(f"حُفظت بيانات {month_label(month)} لـ{names[gd]} ({storage_label()}).")
            st.rerun()


def _structure():
    perf = ss.perf
    names = dict(zip(perf.gds["gd_id"], perf.gds["gd_name"]))
    section("الإدارة العامة")
    c1, c2, c3 = st.columns([1.2, 1.6, 0.8])
    gd = c1.selectbox("اختر الإدارة العامة", list(names), format_func=lambda g: f"{names[g]} ({g})", key="st_gd")
    new_name = c2.text_input("الاسم الجديد", value=names[gd], key=f"st_gdname_{gd}_{ss.get('st_ver', 0)}")
    c3.write("")
    if c3.button("حفظ الاسم", key="st_gdsave", width="stretch"):
        try:
            set_perf(rename_gd(perf, gd, new_name))
            flash("تم تحديث اسم الإدارة العامة مع الحفاظ على معرفها وتاريخها.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))
    section("الأقسام التابعة", "المعرف ثابت ولا يتغير، فيبقى التاريخ مرتبطًا بالقسم عند تغيير اسمه")
    d = perf.depts[perf.depts["gd_id"] == gd][["dept_id", "dept_name", "sort_order", "active"]].sort_values(["sort_order", "dept_id"]).reset_index(drop=True)
    sv = ss.get("st_ver", 0)
    with st.form(f"form_depts_{gd}_{sv}"):
        rows = []
        for r in d.itertuples():
            c0, c1, c2, c3 = st.columns([0.7, 3, 1, 1])
            c0.html(f'<div class="oprow" style="padding-top:34px"><b>{esc(r.dept_id)}</b></div>')
            nm = c1.text_input("اسم القسم", value=r.dept_name, key=f"st_nm_{gd}_{sv}_{r.dept_id}")
            od = c2.number_input("الترتيب", min_value=0, value=int(r.sort_order), step=1, key=f"st_od_{gd}_{sv}_{r.dept_id}")
            ac = c3.checkbox("فعال", value=bool(r.active), key=f"st_ac_{gd}_{sv}_{r.dept_id}")
            rows.append({"dept_id": r.dept_id, "dept_name": nm, "sort_order": od, "active": ac})
        if st.form_submit_button("حفظ تعديلات الأقسام", type="primary"):
            try:
                set_perf(update_depts(perf, pd.DataFrame(rows)))
                ss.st_ver = sv + 1
                flash("حُفظت تعديلات الأقسام. السجل التاريخي بقي مرتبطًا بالمعرفات نفسها.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    c1, c2 = st.columns(2, gap="large")
    with c1:
        section("إضافة قسم")
        with st.form("form_add_dept", clear_on_submit=True):
            nm = st.text_input("اسم القسم الجديد")
            if st.form_submit_button("إضافة القسم إلى الإدارة المختارة"):
                try:
                    new, did = add_dept(perf, gd, nm)
                    set_perf(new)
                    flash(f"أُضيف القسم بالمعرف الثابت {did}.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
    with c2:
        section("إضافة إدارة عامة")
        with st.form("form_add_gd", clear_on_submit=True):
            nm = st.text_input("اسم الإدارة العامة الجديدة")
            if st.form_submit_button("إضافة الإدارة العامة"):
                try:
                    new, gid = add_gd(perf, nm)
                    set_perf(new)
                    flash(f"أُضيفت الإدارة العامة بالمعرف {gid}. أضف لها أقسامًا من الأعلى بعد اختيارها.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
    note("الأسماء الحالية تجريبية ولا تمثل الهيكل التنظيمي لأمانة منطقة حائل.", "info")


def _import():
    note("ارفع ملف CSV لجدول النتائج، أو ملف Excel يحتوي ورقة «performance_records» (واختياريًا «departments» و«general_departments»). "
         "يُتحقق من الملف كاملًا أولًا؛ عند أي خطأ لا يتغير شيء من البيانات الحالية. عند النجاح تستبدل الصفوف المرفوعة نفس (القسم، الشهر) فقط.", "info")
    files = st.file_uploader("ملف نتائج الأداء", type=["csv", "xlsx"], accept_multiple_files=True, key=f"pi_files_{ss.get('pi_ver', 0)}")
    if files and st.button("التحقق من الملف", key="pi_check", type="primary"):
        try:
            raw = read_perf_files(files)
            new, rep, info = merge_records_upload(ss.perf, raw)
        except Exception as e:  # noqa: BLE001
            new, rep, info = None, None, {}
            st.error(f"تعذرت قراءة الملف: {e}")
        if rep is not None:
            if not rep.ok:
                st.error("رُفض الملف ولم تتغير البيانات الحالية. الأخطاء:")
                html("<div class='note bad'><ul>" + "".join(f"<li>{esc(e)}</li>" for e in rep.errors) + "</ul></div>")
                ss.pi_pending = None
            else:
                ss.pi_pending = (new, info, rep.warnings)
    pend = ss.get("pi_pending")
    if pend:
        new, info, warns = pend
        html(f"<div class='note ok'><b>الملف صالح.</b> {info['rows']} صفًا لـ{info['dept_months']} (قسم، شهر) في الأشهر: {esc('، '.join(month_label(m) for m in info['months']))}. "
             f"سيُستبدل {info['replaced_rows']} صفًا موجودًا.</div>")
        for w in warns:
            st.warning(w)
        c1, c2 = st.columns(2)
        if c1.button("تأكيد الاستيراد", type="primary", key="pi_confirm", width="stretch"):
            set_perf(new)
            ss.pi_pending = None
            ss.pi_ver = ss.get("pi_ver", 0) + 1
            flash("تم الاستيراد بنجاح.")
            st.rerun()
        if c2.button("إلغاء", key="pi_cancel", width="stretch"):
            ss.pi_pending = None
            st.rerun()


def _templates():
    perf = ss.perf
    section("القوالب")
    c1, c2 = st.columns(2)
    sample = perf.records.head(0).copy()
    tmpl = pd.DataFrame([{"dept_id": d, "month": "2026-10", "kpi_id": k, "target": "", "actual": "", "data_label": perf.label or "synthetic"}
                         for d in perf.depts.loc[perf.depts["active"].astype(bool), "dept_id"] for k in perf.kpis["kpi_id"]], columns=PERF_RECORDS.col_names)
    _ = sample
    c1.download_button("تنزيل قالب CSV للنتائج الشهرية", csv_bytes(tmpl), "performance_records_template.csv", "text/csv", width="stretch")
    c2.download_button("تنزيل قالب Excel (مع الأقسام والتعليمات)", perf_template_excel(perf), "performance_template.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    section("النسخ الاحتياطي والاستعادة", "يشمل الإدارات والأقسام والمؤشرات وكل النتائج الشهرية")
    c1, c2 = st.columns(2)
    c1.download_button("تنزيل نسخة احتياطية كاملة (Excel)", perf_backup_excel(perf), f"performance_backup_{date.today().isoformat()}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch", type="primary")
    with c2:
        f = st.file_uploader("استعادة من نسخة احتياطية (Excel)", type=["xlsx"], key=f"pr_file_{ss.get('pr_ver', 0)}")
        if f is not None and st.button("التحقق والاستعادة", key="pr_do"):
            try:
                new, rep = validate_perf_bundle(read_perf_files([f]))
            except Exception as e:  # noqa: BLE001
                new, rep = None, None
                st.error(f"تعذرت قراءة الملف: {e}")
            if rep is not None and not rep.ok:
                st.error("رُفضت النسخة ولم تتغير البيانات الحالية:")
                html("<div class='note bad'><ul>" + "".join(f"<li>{esc(e)}</li>" for e in rep.errors) + "</ul></div>")
            elif new is not None:
                set_perf(new)
                ss.pr_ver = ss.get("pr_ver", 0) + 1
                flash("تمت الاستعادة: استُبدلت بيانات الأداء كاملة بمحتوى النسخة.")
                st.rerun()
    section("إعادة البيانات التجريبية")
    if st.button("استعادة بيانات الأداء التجريبية الأصلية", key="pr_reset"):
        set_perf(_synthetic_perf())
        flash("أُعيدت بيانات الأداء التجريبية. بيانات الإيرادات لم تتغير.")
        st.rerun()
    rows = [[esc(r.kpi_id), f"<b>{esc(r.kpi_name)}</b>", esc(r.definition), esc(r.unit), f"{r.default_weight:g}%"] for r in perf.kpis.itertuples()]
    section("تعريف المؤشرات")
    html(table([("المعرف", ""), ("المؤشر", ""), ("التعريف", ""), ("الوحدة", "c"), ("الوزن الافتراضي", "c")], rows))
