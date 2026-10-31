"""الإيرادات: المستهدف، المحقق، الفجوة، والمصادر."""
from __future__ import annotations

import streamlit as st

from core.formatting import esc, fmt_int, fmt_m, fmt_pct
from core.revenue import compute_kpis, scenario_result, sources_table

from .. import charts
from ..components import html, kpi_grid, kpi_money, table
from ..state import opportunities, ss


def render():
    data = ss.rev_data
    s = data.settings
    k = compute_kpis(data)
    opps, _ = opportunities()
    res = scenario_result(opps, ss.selection, ss.multipliers[ss.scenario], k, s.financial_basis)
    att = "—" if k["attainment_pct"] is None else fmt_pct(k["attainment_pct"], 0)

    kpi_grid([
        kpi_money("المستهدف السنوي", k["target"], "primary"),
        kpi_money("المحقق حتى الآن", k["realized"], "ok", extra=f"{att} من المستهدف"),
        kpi_money("الفجوة الحالية", k["gap_to_date"], "alert"),
        kpi_money("المتبقي بنهاية السنة", res["remaining_gap"], "gold", extra=f"بعد المتوقع أصلًا والفرص المختارة ({esc(fmt_m(res['contribution']))})"),
    ])

    with st.container(key="card_gap"):
        html('<div class="card-title">كيف تُسد الفجوة؟</div><div class="card-sub">الخط الذهبي = المستهدف (مليون ريال)</div>')
        charts.show(charts.gap_simple(k, res["recurring_in_year"], res["one_time_in_year"], s.financial_basis), "rev_gap")

    with st.container(key="card_sources"):
        html('<div class="card-title">المحقق مقابل المستهدف حسب المصدر</div>')
        charts.show(charts.sources_vs_target(data.sources), "rev_sources")

    with st.expander("تفاصيل المصادر بالأرقام"):
        df = sources_table(data)
        rows = [[esc(r.source_name), fmt_int(r.annual_target_sar), fmt_int(r.realized_to_date_sar),
                 fmt_pct(r.attainment_pct, 0) if r.attainment_pct is not None else "—", fmt_int(r.expected_remaining_sar)]
                for r in df.sort_values("annual_target_sar", ascending=False).itertuples()]
        html(table([("المصدر", ""), ("المستهدف (ريال)", "num"), ("المحقق (ريال)", "num"), ("التحقيق", "num"), ("متوقع لبقية السنة (ريال)", "num")], rows))

    with st.expander("كيف تُحسب الأرقام؟"):
        html('<div class="note info"><ul>'
             "<li><b>الفجوة الحالية</b> = المستهدف − المحقق حتى تاريخ البيانات.</li>"
             "<li><b>المتوقع أصلًا</b> = ما سيُحصَّل من العقود والرسوم القائمة حتى نهاية السنة دون فرص جديدة.</li>"
             "<li><b>المتبقي بنهاية السنة</b> = المستهدف − المحقق − المتوقع أصلًا − ما تضيفه الفرص المختارة هذه السنة.</li>"
             "<li>الأساس المالي نقدي، والمبالغ إيرادات قبل التكاليف.</li></ul></div>")
