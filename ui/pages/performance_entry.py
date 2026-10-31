"""إدخال البيانات: إدخال شهر، الأقسام، ورفع وتنزيل الملفات."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core.exports import csv_bytes, perf_backup_excel, revenue_template_excel
from core.formatting import AR_MONTHS, esc, month_label
from core.performance import (add_dept, add_gd, merge_records_upload, month_wide, read_perf_files, rename_gd, update_depts,
                              upsert_month, validate_perf_bundle)
from core.revenue_data import read_revenue_files, validate_revenue_bundle
from core.schemas import PERF_RECORDS

from ..components import html
from ..state import _synthetic_perf, flash, reset_revenue, set_perf, show_flash, ss, storage_label

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def render():
    show_flash()
    t1, t2, t3 = st.tabs(["إدخال شهر", "الأقسام", "الملفات"])
    with t1:
        _month_entry()
    with t2:
        _structure()
    with t3:
        _files()
    st.caption(f"الحفظ: {storage_label()}.")


def _errors(errs):
    html("<div class='note bad'><ul>" + "".join(f"<li>{esc(e)}</li>" for e in errs) + "</ul></div>")


def _default_target(perf, depts, month, kpi_id):
    """آخر مستهدف معروف للمؤشر في هذه الإدارة (للشهر نفسه أولًا)."""
    r = perf.records[perf.records["dept_id"].isin(depts) & (perf.records["kpi_id"] == kpi_id) & perf.records["target"].notna()]
    same = r[r["month"] == month]
    src = same if len(same) else r[r["month"] <= month].sort_values("month")
    if src.empty:
        return None
    return float(src["target"].mode().iloc[0]) if len(same) else float(src["target"].iloc[-1])


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
        st.info("لا توجد أقسام في هذه الإدارة. أضفها من تبويب «الأقسام».")
        return
    kpis = list(perf.kpis.itertuples())
    ver = ss.get("pe_ver", 0)
    with st.form(f"form_month_{gd}_{month}_{ver}"):
        html('<div class="card-title">المستهدف لكل الأقسام</div>')
        tcols = st.columns(len(kpis))
        targets = {}
        for i, r in enumerate(kpis):
            targets[r.kpi_id] = tcols[i].number_input(r.kpi_name, 0.0, 100.0, _default_target(perf, list(wide["dept_id"]), month, r.kpi_id),
                                                      0.5, format="%.1f", placeholder="غير مدخل", key=f"pe_{gd}_{month}_{ver}_{r.kpi_id}_target",
                                                      help=r.definition)
        html('<div class="card-title" style="margin-top:10px">المحقق الفعلي</div>')
        hcols = st.columns([1.6] + [1] * len(kpis))
        for i, r in enumerate(kpis):
            hcols[i + 1].html(f'<div class="muted" style="font-size:12.5px">{esc(r.kpi_name)}</div>')
        values = []
        for d in wide.itertuples(index=False):
            dd = d._asdict()
            cols = st.columns([1.6] + [1] * len(kpis), vertical_alignment="bottom")
            cols[0].html(f'<div class="opval" style="padding-bottom:10px"><b>{esc(d.dept_name)}</b></div>')
            row = {"dept_id": d.dept_id}
            for i, r in enumerate(kpis):
                cur = dd[f"{r.kpi_id}_actual"]
                row[f"{r.kpi_id}_actual"] = cols[i + 1].number_input(
                    r.kpi_name, 0.0, 100.0, None if cur != cur else float(cur), 0.5, format="%.1f", placeholder="غير مدخل",
                    key=f"pe_{gd}_{month}_{ver}_{d.dept_id}_{r.kpi_id}_actual", label_visibility="collapsed")
            values.append(row)
        st.caption("القيم من 0 إلى 100. اترك الحقل فارغًا إذا لم تتوفر القيمة — لا يُحتسب صفرًا.")
        submitted = st.form_submit_button("حفظ بيانات الشهر", type="primary")
    if submitted:
        rows = []
        for v in values:
            row = {"dept_id": v["dept_id"]}
            for r in kpis:
                row[f"{r.kpi_id}_target"] = targets[r.kpi_id]
                row[f"{r.kpi_id}_actual"] = v[f"{r.kpi_id}_actual"]
            rows.append(row)
        edited = pd.DataFrame(rows)
        edited = edited.astype({c: float for c in edited.columns if c != "dept_id"})
        new, errs = upsert_month(perf, month, edited)
        if errs:
            _errors(errs)
        else:
            set_perf(new)
            ss.pe_ver = ver + 1
            flash(f"حُفظت بيانات {month_label(month)}.")
            st.rerun()


def _structure():
    perf = ss.perf
    names = dict(zip(perf.gds["gd_id"], perf.gds["gd_name"]))
    sv = ss.get("st_ver", 0)
    c1, c2, c3 = st.columns([1.2, 1.6, 0.8], vertical_alignment="bottom")
    gd = c1.selectbox("الإدارة العامة", list(names), format_func=lambda g: names[g], key="st_gd")
    new_name = c2.text_input("اسم الإدارة", value=names[gd], key=f"st_gdname_{gd}_{sv}")
    if c3.button("حفظ الاسم", key="st_gdsave", width="stretch"):
        try:
            set_perf(rename_gd(perf, gd, new_name))
            flash("تم تحديث الاسم.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))
    d = perf.depts[perf.depts["gd_id"] == gd][["dept_id", "dept_name", "sort_order", "active"]].sort_values(["sort_order", "dept_id"]).reset_index(drop=True)
    with st.form(f"form_depts_{gd}_{sv}"):
        rows = []
        for r in d.itertuples():
            a, b = st.columns([4, 1], vertical_alignment="bottom")
            nm = a.text_input(f"اسم القسم ({r.dept_id})", value=r.dept_name, key=f"st_nm_{gd}_{sv}_{r.dept_id}")
            ac = b.checkbox("فعال", value=bool(r.active), key=f"st_ac_{gd}_{sv}_{r.dept_id}")
            rows.append({"dept_id": r.dept_id, "dept_name": nm, "sort_order": r.sort_order, "active": ac})
        if st.form_submit_button("حفظ تعديلات الأقسام", type="primary"):
            try:
                set_perf(update_depts(perf, pd.DataFrame(rows)))
                ss.st_ver = sv + 1
                flash("حُفظت التعديلات. السجل السابق بقي مرتبطًا بكل قسم.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    with st.expander("إضافة قسم أو إدارة عامة"):
        a, b = st.columns(2)
        with a.form("form_add_dept", clear_on_submit=True):
            nm = st.text_input("قسم جديد في الإدارة المختارة")
            if st.form_submit_button("إضافة القسم"):
                try:
                    new, did = add_dept(perf, gd, nm)
                    set_perf(new)
                    flash(f"أُضيف القسم ({did}).")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        with b.form("form_add_gd", clear_on_submit=True):
            nm = st.text_input("إدارة عامة جديدة")
            if st.form_submit_button("إضافة الإدارة"):
                try:
                    new, gid = add_gd(perf, nm)
                    set_perf(new)
                    flash(f"أُضيفت الإدارة ({gid}).")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))


def _files():
    perf = ss.perf
    left, right = st.columns(2, gap="large")
    with left:
        html('<div class="card-title">بيانات الأداء</div>')
        tmpl = pd.DataFrame([{"dept_id": d, "month": "2026-10", "kpi_id": k, "target": "", "actual": "", "data_label": perf.label or "synthetic"}
                             for d in perf.depts.loc[perf.depts["active"].astype(bool), "dept_id"] for k in perf.kpis["kpi_id"]], columns=PERF_RECORDS.col_names)
        st.download_button("تنزيل القالب (CSV)", csv_bytes(tmpl), "performance_template.csv", "text/csv", width="stretch", on_click="ignore")
        st.download_button("تنزيل نسخة احتياطية (Excel)", perf_backup_excel(perf), f"performance_backup_{date.today().isoformat()}.xlsx", XLSX, width="stretch", on_click="ignore")
        files = st.file_uploader("رفع نتائج أو نسخة احتياطية (CSV / Excel)", type=["csv", "xlsx"], accept_multiple_files=True, key=f"pi_files_{ss.get('pi_ver', 0)}")
        if files and st.button("التحقق من الملف", key="pi_check", type="primary"):
            try:
                raw = read_perf_files(files)
                if {"general_departments", "departments", "kpi_definitions", "performance_records"} <= set(raw):
                    new, rep = validate_perf_bundle(raw)
                    info = {"full": True}
                else:
                    new, rep, info = merge_records_upload(perf, raw)
            except Exception as e:  # noqa: BLE001
                new, rep, info = None, None, {}
                st.error(f"تعذرت قراءة الملف: {e}")
            if rep is not None and not rep.ok:
                ss.pi_pending = None
                st.error("رُفض الملف ولم تتغير البيانات:")
                _errors(rep.errors)
            elif new is not None:
                ss.pi_pending = (new, info)
        pend = ss.get("pi_pending")
        if pend:
            new, info = pend
            st.success("الملف صالح." + ("" if info.get("full") else f" سيُحدّث {info['dept_months']} (قسم، شهر)."))
            a, b = st.columns(2)
            if a.button("تأكيد", type="primary", key="pi_confirm", width="stretch"):
                set_perf(new)
                ss.pi_pending = None
                ss.pi_ver = ss.get("pi_ver", 0) + 1
                flash("تم الاستيراد.")
                st.rerun()
            if b.button("إلغاء", key="pi_cancel", width="stretch"):
                ss.pi_pending = None
                st.rerun()
        if st.button("إعادة البيانات التجريبية للأداء", key="pr_reset"):
            set_perf(_synthetic_perf())
            flash("أُعيدت بيانات الأداء التجريبية.")
            st.rerun()
    with right:
        html('<div class="card-title">بيانات الإيرادات</div>')
        st.download_button("تنزيل القالب (Excel)", revenue_template_excel(), "revenue_template.xlsx", XLSX, width="stretch", on_click="ignore")
        rfiles = st.file_uploader("رفع بيانات الإيرادات (Excel أو CSV)", type=["xlsx", "csv"], accept_multiple_files=True, key=f"ri_files_{ss.get('ri_ver', 0)}")
        if rfiles and st.button("التحقق من الملفات", key="ri_check", type="primary"):
            try:
                data, rep = validate_revenue_bundle(read_revenue_files(rfiles))
            except Exception as e:  # noqa: BLE001
                data, rep = None, None
                st.error(f"تعذرت قراءة الملفات: {e}")
            if rep is not None and not rep.ok:
                ss.ri_pending = None
                st.error("رُفض الاستيراد ولم تتغير البيانات:")
                _errors(rep.errors)
            elif data is not None:
                ss.ri_pending = data
        if ss.get("ri_pending") is not None:
            st.success("الملفات صالحة.")
            a, b = st.columns(2)
            if a.button("تأكيد", type="primary", key="ri_confirm", width="stretch"):
                reset_revenue(ss.ri_pending, source="upload")
                ss.ri_pending = None
                ss.ri_ver = ss.get("ri_ver", 0) + 1
                flash("استُبدلت بيانات الإيرادات.")
                st.rerun()
            if b.button("إلغاء", key="ri_cancel", width="stretch"):
                ss.ri_pending = None
                st.rerun()
        if st.button("إعادة البيانات التجريبية للإيرادات", key="rev_reset"):
            reset_revenue()
            flash("أُعيدت بيانات الإيرادات التجريبية.")
            st.rerun()
    st.caption("يُتحقق من الملف كاملًا قبل الحفظ؛ عند أي خطأ لا يتغير شيء. النسخة المنشورة تقبل البيانات التجريبية فقط.")
