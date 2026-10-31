"""الفرص: اختيار الفرص والسيناريو، والإيراد الإضافي والفجوة المتبقية."""
from __future__ import annotations

import streamlit as st

from core.config import SCENARIOS_DEFAULT
from core.formatting import esc, fmt_int, fmt_sar
from core.opportunities import EASE_LABELS, RISK_LABELS
from core.revenue import auto_select, compute_kpis, scenario_result

from ..components import calc_block, html, kpi, kpi_grid, kpi_money, note, rich, table
from ..state import opportunities, ss

SHORT_TYPE = {"lease": "تأجير", "renewal": "تجديد عقد", "collection": "تحصيل"}


def _set_selection(ids):
    ss.selection = list(ids)
    ss.sel_version += 1


def _toggle(oid):
    key = f"sel_{oid}_{ss.sel_version}"
    cur = list(ss.selection)
    if ss[key] and oid not in cur:
        cur.append(oid)
    elif not ss[key] and oid in cur:
        cur.remove(oid)
    ss.selection = cur


def render():
    data = ss.rev_data
    s = data.settings
    k = compute_kpis(data)
    opps, excluded = opportunities()

    c1, c2, c3 = st.columns([2.2, 1, 1])
    with c1:
        sc = st.segmented_control("السيناريو", list(SCENARIOS_DEFAULT), default=ss.scenario, key="sc_pick",
                                  format_func=lambda x: f"{SCENARIOS_DEFAULT[x]['label']} {ss.multipliers[x]:.0%}")
        if sc and sc != ss.scenario:
            ss.scenario = sc
            st.rerun()
    mult = ss.multipliers[ss.scenario]
    with c2:
        st.write("")
        if st.button("اختيار الأعلى أولوية", type="primary", width="stretch"):
            _set_selection(auto_select(opps, k, mult, s.financial_basis))
            st.rerun()
    with c3:
        st.write("")
        if st.button("إلغاء الكل", width="stretch"):
            _set_selection([])
            st.rerun()

    res = scenario_result(opps, ss.selection, mult, k, s.financial_basis)
    kpi_grid([
        kpi("الفرص المختارة", f"{len(res['selection'].kept)} من {len(opps)}", "", "primary"),
        kpi_money("الإيراد الإضافي هذه السنة", res["contribution"], "ok"),
        kpi_money("الفجوة المتبقية", res["remaining_gap"], "alert" if res["remaining_gap"] > 0 else "ok"),
    ])
    if res["remaining_gap"] > 0:
        note("الفرص المختارة <b>لا تكفي</b> لسد الفجوة هذه السنة.", "warn")
    if res["selection"].dropped:
        note("لم تُحتسب فرص متعارضة على الأصل نفسه: " + "، ".join(esc(a) for a, _ in res["selection"].dropped), "bad")

    if opps.empty:
        note("لا توجد فرص في البيانات الحالية.", "info")
    else:
        det = res["detail"].set_index("opp_id") if not res["detail"].empty else None
        html('<div class="ophead"><span>الفرصة</span><span>النوع</span><span>هذه السنة</span><span>سنويًا / الإجمالي</span></div>')
        for o in opps.itertuples():
            with st.container(key=f"oprow_{o.opp_id}"):
                a, b, c, d = st.columns([3.4, 1.1, 1.3, 1.3], vertical_alignment="center")
                a.checkbox(o.title, value=o.opp_id in ss.selection, key=f"sel_{o.opp_id}_{ss.sel_version}", on_change=_toggle, args=(o.opp_id,))
                b.html(f'<span class="tag {"gold" if o.nature == "one_time" else ""}">{SHORT_TYPE[o.opp_type]}</span>')
                v = det.at[o.opp_id, "in_year"] if (det is not None and o.opp_id in det.index) else o.in_year
                c.html(f'<div class="opval">{fmt_int(v)}<small>ريال</small></div>')
                total = o.annual_potential if o.nature == "recurring" else o.one_time_total
                d.html(f'<div class="opval">{fmt_int(total)}<small>{"سنويًا" if o.nature == "recurring" else "مرة واحدة"}</small></div>')

        with st.expander("تفاصيل فرصة"):
            oid = st.selectbox("الفرصة", list(opps["opp_id"]), format_func=lambda x: opps.set_index("opp_id").at[x, "title"], key="opp_detail")
            o = opps.set_index("opp_id").loc[oid]
            ev = "".join(f"<dt>{esc(a)}</dt><dd>{rich(b)}</dd>" for a, b in o["evidence"])
            html(f"""<div class="opp"><p style="margin:0 0 8px"><b>السبب:</b> {rich(o['reason'])}</p>
<div class="grid2"><div><h5>الحساب</h5>{calc_block(o['method'])}</div><div><h5>الأدلة من البيانات</h5><dl>{ev}</dl></div></div>
<div class="grid2"><div><h5>الافتراضات</h5><ul>{''.join(f'<li>{rich(x)}</li>' for x in o['assumptions'])}</ul></div>
<div><h5>الموافقات المطلوبة</h5><ul>{''.join(f'<li>{esc(x)}</li>' for x in o['approvals'])}</ul>
<p class="muted" style="margin-top:6px">السهولة: {EASE_LABELS[o['ease']]} · المخاطر: {RISK_LABELS[o['risk']]} · بدء الأثر: <bdi dir="ltr">{o['effective_date'].isoformat()}</bdi></p></div></div>
<div class="disclaimer">اقتراح تحليلي وليس موافقة أو إذنًا بالتنفيذ.</div></div>""")

    with st.expander(f"المستبعد ولماذا ({len(excluded)})"):
        html(table([("المرجع", ""), ("السبب", "")], [[esc(a), esc(c)] for a, b, c in excluded.itertuples(index=False)]))

    with st.expander("كيف تُحسب الفرص والترتيب؟"):
        w = ss.priority_weights
        html('<div class="note info"><ul>'
             "<li><b>تأجير:</b> المساحة × الإيجار المرجعي × الإشغال − الإيراد الحالي.</li>"
             "<li><b>تجديد:</b> الفرق بين القيمة المرجعية وقيمة العقد، ولا يُحتسب قبل تاريخ التجديد.</li>"
             "<li><b>تحصيل:</b> الرصيد غير المسدد × نسبة استرداد حسب عمر الدين، بعد طرح المتوقع أصلًا.</li>"
             "<li><b>هذه السنة</b> = ما يتحقق بعد مهلة التنفيذ حتى 31 ديسمبر فقط.</li>"
             f"<li><b>الترتيب:</b> {w['contribution']}% مساهمة هذه السنة + {w['ease']}% السهولة + {w['risk']}% انخفاض المخاطر (درجة نسبية، ليست احتمال نجاح).</li>"
             "<li><b>السيناريو:</b> 70% أو 100% أو 120% من التقدير، بسقوف منطقية. افتراضات وليست توقعات مؤكدة.</li>"
             "<li>قواعد تحليلية قابلة للتفسير — لا يوجد نموذج ذكاء اصطناعي مدرب.</li></ul></div>")
