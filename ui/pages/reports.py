"""التقارير: PDF وExcel للإيرادات (السيناريو المختار)، وExcel وPDF لملخص أداء الشهر والإدارة."""
from __future__ import annotations

import streamlit as st

from core.config import SCENARIOS_DEFAULT
from core.exports import perf_excel, revenue_excel
from core.formatting import date_ar, esc, fmt_sar, month_label
from core.pdf_report import perf_pdf, revenue_pdf
from core.performance import month_summary
from core.revenue import compute_kpis, scenario_result

from ..components import html, kpi, kpi_grid, kpi_money, note, section
from ..state import opportunities, ss
from .performance_dashboard import gd_month_pickers

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def render():
    t1, t2 = st.tabs(["تقارير الإيرادات", "تقارير أداء الإدارات"])
    with t1:
        _revenue()
    with t2:
        _perf()


def _revenue():
    data = ss.rev_data
    s = data.settings
    k = compute_kpis(data)
    opps, excluded = opportunities()
    sc = ss.scenario
    mults = ss.multipliers
    res = scenario_result(opps, ss.selection, mults[sc], k, s.financial_basis)
    # بصمة الحالة: الملف المنشأ يُعرض للتنزيل فقط إذا طابق الحالة الحالية (لا ملفات قديمة بعد تغيير الاختيار)
    sig = (tuple(ss.selection), sc, tuple(sorted(mults.items())), tuple(sorted(ss.priority_weights.items())), repr(s), repr(sorted(ss.engine_params.items())))
    note(f"يتضمن التقرير: الفجوة، الفرص (المختارة مميزة عن غيرها)، الأدلة، طريقة الحساب، الافتراضات، الموافقات المطلوبة، المستبعد، والسيناريو المختار. "
         f"<b>تاريخ البيانات:</b> {esc(date_ar(s.snapshot_date))} — <b>المصدر:</b> {esc(s.source_note)}. التقديرات ليست حقائق مالية مؤكدة.", "info")
    kpi_grid([
        kpi("السيناريو المختار", esc(SCENARIOS_DEFAULT[sc]["label"]), f"معامل {mults[sc]:.0%} — يُغيَّر من صفحة السيناريوهات", "primary"),
        kpi("الفرص المختارة", f"{len(res['selection'].kept)}", f"من أصل {len(opps)} فرصة مكتشفة", "neutral"),
        kpi_money("المحتسب في سد الفجوة", res["contribution"], "ok"),
        kpi_money("الفجوة المتبقية", res["remaining_gap"], "alert" if res["remaining_gap"] > 0 else "ok"),
    ])
    c1, c2 = st.columns(2)
    with c1:
        if st.button("إنشاء تقرير PDF", type="primary", width="stretch", key="mk_rev_pdf"):
            with st.spinner("جارٍ إنشاء التقرير..."):
                ss.rev_pdf = (sig, revenue_pdf(data, k, opps, excluded, sc, mults, res, ss.priority_weights))
        if ss.get("rev_pdf") and ss.rev_pdf[0] == sig:
            st.download_button("تنزيل تقرير الإيرادات PDF", ss.rev_pdf[1], f"revenue_report_{s.snapshot_date.isoformat()}_{sc}.pdf", "application/pdf", width="stretch", key="dl_rev_pdf")
    with c2:
        if st.button("إنشاء ملف Excel (النتائج والمدخلات)", width="stretch", key="mk_rev_xlsx"):
            with st.spinner("جارٍ إنشاء الملف..."):
                allr = {key: scenario_result(opps, ss.selection, m, k, s.financial_basis) for key, m in mults.items()}
                ss.rev_xlsx = (sig, revenue_excel(data, k, opps, excluded, sc, mults, res, allr, ss.priority_weights, ss.engine_params))
        if ss.get("rev_xlsx") and ss.rev_xlsx[0] == sig:
            st.download_button("تنزيل ملف Excel", ss.rev_xlsx[1], f"revenue_results_{s.snapshot_date.isoformat()}_{sc}.xlsx", XLSX, width="stretch", key="dl_rev_xlsx")
    st.caption("يُنشأ الملف من الحالة الحالية، ويختفي زر التنزيل تلقائيًا إذا تغيّر الاختيار أو السيناريو أو الإعدادات حتى يُعاد الإنشاء.")


def _perf():
    perf, s = ss.perf, ss.perf_settings
    gd, month, _ = gd_month_pickers("rp")
    if month is None:
        note("لا توجد بيانات أداء لهذه الإدارة العامة.", "warn")
        return
    sm = month_summary(perf, gd, month, s)
    note(f"يتضمن التصدير: نتائج الأقسام والحالة وسبب التصنيف، المؤشرات والمستهدفات والمحقق، الأوزان وحدود التصنيف، وتاريخ التصدير ومصدر البيانات — لشهر {esc(month_label(month))}.", "info")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("تنزيل ملخص الشهر Excel", perf_excel(perf, gd, month, s, sm), f"performance_{gd}_{month}.xlsx", XLSX,
                           type="primary", width="stretch", key="dl_perf_xlsx")
    with c2:
        if st.button("إنشاء ملخص PDF", width="stretch", key="mk_perf_pdf"):
            ss.perf_pdf = (gd, month, perf_pdf(perf, gd, month, s, sm))
        p = ss.get("perf_pdf")
        if p and p[0] == gd and p[1] == month:
            st.download_button("تنزيل ملخص الأداء PDF", p[2], f"performance_{gd}_{month}.pdf", "application/pdf", width="stretch", key="dl_perf_pdf")
