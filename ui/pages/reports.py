"""التقارير: تنزيل PDF وExcel."""
from __future__ import annotations

import streamlit as st

from core.config import SCENARIOS_DEFAULT
from core.exports import perf_excel, revenue_excel
from core.formatting import month_label
from core.pdf_report import perf_pdf, revenue_pdf
from core.performance import month_summary
from core.revenue import compute_kpis, scenario_result

from ..components import html
from ..state import opportunities, ss
from .performance_dashboard import gd_month_pickers

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@st.cache_data(show_spinner=False, max_entries=8)
def _rev_files(sig, _args):
    data, k, opps, excluded, sc, mults, res, allr, weights, params = _args
    return (revenue_pdf(data, k, opps, excluded, sc, mults, res, weights),
            revenue_excel(data, k, opps, excluded, sc, mults, res, allr, weights, params))


def render():
    left, right = st.columns(2, gap="large")
    with left:
        with st.container(key="card_rep_rev"):
            data = ss.rev_data
            s = data.settings
            k = compute_kpis(data)
            opps, excluded = opportunities()
            sc, mults = ss.scenario, ss.multipliers
            res = scenario_result(opps, ss.selection, mults[sc], k, s.financial_basis)
            html(f'<div class="card-title">تقرير الإيرادات والفرص</div><div class="card-sub">السيناريو {SCENARIOS_DEFAULT[sc]["label"]} · '
                 f'{len(res["selection"].kept)} فرص مختارة · البيانات حتى {s.snapshot_date.isoformat()}</div>')
            allr = {key: scenario_result(opps, ss.selection, m, k, s.financial_basis) for key, m in mults.items()}
            sig = (tuple(ss.selection), sc, tuple(sorted(mults.items())), repr(s), len(data.assets), len(data.receivables))
            pdf, xlsx = _rev_files(sig, (data, k, opps, excluded, sc, mults, res, allr, ss.priority_weights, ss.engine_params))
            st.download_button("تنزيل PDF", pdf, f"revenue_report_{sc}.pdf", "application/pdf", type="primary", width="stretch", on_click="ignore", key="dl_rev_pdf")
            st.download_button("تنزيل Excel", xlsx, f"revenue_results_{sc}.xlsx", XLSX, width="stretch", on_click="ignore", key="dl_rev_xlsx")
    with right:
        with st.container(key="card_rep_perf"):
            html('<div class="card-title">تقرير أداء الأقسام</div><div class="card-sub">النتائج والمؤشرات والأوزان وحدود الألوان</div>')
            perf, ps = ss.perf, ss.perf_settings
            gd, month = gd_month_pickers("rp")
            if month is None:
                st.info("لا توجد بيانات لهذه الإدارة.")
                return
            sm = month_summary(perf, gd, month, ps)
            st.download_button("تنزيل PDF", perf_pdf(perf, gd, month, ps, sm), f"performance_{gd}_{month}.pdf", "application/pdf",
                               type="primary", width="stretch", on_click="ignore", key="dl_perf_pdf")
            st.download_button("تنزيل Excel", perf_excel(perf, gd, month, ps, sm), f"performance_{gd}_{month}.xlsx", XLSX,
                               width="stretch", on_click="ignore", key="dl_perf_xlsx")
            st.caption(month_label(month))
