"""السيناريوهات: اختيار الفرص، الاختيار التلقائي، معاملات الحساسية، والفجوة المتبقية أو الفائض."""
from __future__ import annotations

import streamlit as st

from core.config import SCENARIOS_DEFAULT
from core.formatting import esc, fmt_int, fmt_sar
from core.opportunities import TYPE_LABELS
from core.revenue import auto_select, compute_kpis, scenario_result

from .. import charts
from ..components import html, kpi, kpi_grid, kpi_money, note, section, table, tag
from ..state import opportunities, ss


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
    opps, _ = opportunities()

    c1, c2 = st.columns([1.2, 1], gap="large")
    with c1:
        sc = st.segmented_control("السيناريو", list(SCENARIOS_DEFAULT), default=ss.scenario,
                                  format_func=lambda x: f"{SCENARIOS_DEFAULT[x]['label']} ({ss.multipliers[x]:.0%})", key="sc_pick")
        if sc and sc != ss.scenario:
            ss.scenario = sc
            st.rerun()
    with c2:
        with st.expander("معاملات الحساسية (افتراضات قابلة للتعديل)"):
            cols = st.columns(3)
            new = {}
            for i, key in enumerate(SCENARIOS_DEFAULT):
                new[key] = cols[i].number_input(f"{SCENARIOS_DEFAULT[key]['label']} %", 0, 300, int(round(ss.multipliers[key] * 100)), 5, key=f"mult_{key}") / 100
            if new != ss.multipliers:
                ss.multipliers = new
                st.rerun()
            if not (new["conservative"] <= new["base"] <= new["optimistic"]):
                st.warning("المعتاد أن يكون: متحفظ ≤ متوسط ≤ متفائل.")
            st.caption("تُطبّق على المحرك الرئيسي لكل فرصة (الإشغال، الزيادة، نسب الاسترداد) مع سقوف منطقية. هذه افتراضات حساسية وليست فواصل ثقة إحصائية.")
    mult = ss.multipliers[ss.scenario]
    res = scenario_result(opps, ss.selection, mult, k, s.financial_basis)

    kpi_grid([
        kpi_money("إجمالي الإيراد الإضافي خلال السنة", res["recurring_in_year"] + res["one_time_in_year"], "primary",
                  extra=f"متكرر {esc(fmt_sar(res['recurring_in_year']))} + لمرة واحدة {esc(fmt_sar(res['one_time_in_year']))}"),
        kpi_money("المحتسب في سد الفجوة", res["contribution"], "ok",
                  extra=("الأساس النقدي: يشمل التحصيل" if s.financial_basis == "cash" else "أساس الاستحقاق: بدون تحصيل الذمم السابقة")),
        kpi_money("الفجوة المتوقعة قبل الفرص", k["projected_gap"], "gold"),
        kpi_money("الفجوة المتبقية", res["remaining_gap"], "alert" if res["remaining_gap"] > 0 else "ok"),
        kpi_money("الفائض", res["surplus"], "ok" if res["surplus"] > 0 else "neutral"),
    ])
    if not res["selection"].kept and k["projected_gap"] > 0:
        note(f"<b>لم تُختر أي فرصة.</b> الفجوة المتوقعة كاملة ({esc(fmt_sar(k['projected_gap']))}) ما تزال متبقية. استخدم الاختيار التلقائي أو اختر الفرص يدويًا.", "warn")
    elif res["remaining_gap"] > 0:
        pct = res["gap_closed_pct"]
        note(f"<b>الفرص المختارة تغطي {pct:.1f}% من الفجوة المتوقعة</b>، ويتبقى {esc(fmt_sar(res['remaining_gap']))}. "
             "يلزم مصادر أو قرارات إضافية لسد الباقي؛ لا يفترض النظام أن الفرص المكتشفة تكفي.", "warn")
    elif k["projected_gap"] > 0:
        note(f"<b>الفرص المختارة تكفي لسد الفجوة المتوقعة</b> وفق هذا السيناريو، مع فائض متوقع {esc(fmt_sar(res['surplus']))}. التحقق الفعلي مرهون بالتنفيذ والموافقات.", "ok")
    else:
        note("لا توجد فجوة متوقعة بنهاية السنة وفق الإيراد الأساسي المتوقع.", "ok")
    if res["selection"].dropped:
        items = "".join(f"<li><b>{esc(a)}</b>: {esc(b)}</li>" for a, b in res["selection"].dropped)
        note(f"<b>لم تُحتسب بعض الفرص المختارة لمنع التكرار أو التعارض:</b><ul>{items}</ul>", "bad")
    if s.financial_basis != "cash" and res["one_time_in_year"] > 0:
        note("على <b>أساس الاستحقاق</b> لا يُحتسب تحصيل الذمم المثبتة سابقًا إيرادًا جديدًا؛ يظهر كأثر نقدي فقط ولا يدخل في سد الفجوة.", "info")

    left, right = st.columns([1.35, 1], gap="large")
    with left:
        section("اختيار الفرص", f"{len(res['selection'].kept)} محتسبة من {len(opps)}")
        b1, b2, b3 = st.columns(3)
        if b1.button("اختيار الأعلى أولوية تلقائيًا", type="primary", width="stretch", help="بالترتيب حتى تغطية الفجوة، مع تخطي المتعارض وما ليس له أثر هذا العام"):
            _set_selection(auto_select(opps, k, mult, s.financial_basis))
            st.rerun()
        if b2.button("اختيار كل ما له أثر هذا العام", width="stretch"):
            ids, groups = [], set()
            for o in opps.sort_values("priority_score", ascending=False).itertuples():
                if o.in_year > 0 and o.conflict_group not in groups and (o.nature == "recurring" or s.financial_basis == "cash"):
                    ids.append(o.opp_id)
                    groups.add(o.conflict_group)
            _set_selection(ids)
            st.rerun()
        if b3.button("إلغاء كل الاختيارات", width="stretch"):
            _set_selection([])
            st.rerun()
        det = res["detail"].set_index("opp_id") if not res["detail"].empty else None
        dropped = dict(res["selection"].dropped)
        for t, lbl in TYPE_LABELS.items():
            sub = opps[opps["opp_type"] == t]
            if sub.empty:
                continue
            html(f'<div class="card-title" style="margin-top:8px">{esc(lbl)} ({len(sub)})</div>')
            for o in sub.itertuples():
                cc1, cc2 = st.columns([3.2, 1.3])
                with cc1:
                    st.checkbox(f"{o.opp_id} · {o.title}", value=o.opp_id in ss.selection, key=f"sel_{o.opp_id}_{ss.sel_version}",
                                on_change=_toggle, args=(o.opp_id,))
                with cc2:
                    if det is not None and o.opp_id in det.index:
                        v = det.at[o.opp_id, "in_year"]
                        cap = " (بلغ السقف)" if det.at[o.opp_id, "capped"] else ""
                        html(f'<div class="oprow"><span>خلال السنة</span><b>{esc(fmt_sar(v))}{cap}</b></div>')
                    elif o.opp_id in dropped:
                        html('<div class="oprow"><span style="color:#B42318">متعارضة — غير محتسبة</span></div>')
                    else:
                        html(f'<div class="oprow"><span>أساسي</span><span>{esc(fmt_sar(o.in_year))}</span></div>')
    with right:
        rows = []
        for key in SCENARIOS_DEFAULT:
            r = scenario_result(opps, ss.selection, ss.multipliers[key], k, s.financial_basis)
            rows.append((f"{SCENARIOS_DEFAULT[key]['label']} ({ss.multipliers[key]:.0%})", r["contribution"], r["remaining_gap"], r["surplus"]))
        with st.container(key="card_scen"):
            html('<div class="card-title">المساهمة المحتسبة في كل سيناريو لنفس الاختيار</div><div class="card-sub">الخط الأحمر = الفجوة المتوقعة بنهاية السنة قبل الفرص (مليون ريال).</div>')
            charts.show(charts.scenario_bars([(a, b) for a, b, _, _ in rows], k["projected_gap"]), "sc_bars")
        html(table([("السيناريو", ""), ("المحتسب (ريال)", "num"), ("الفجوة المتبقية (ريال)", "num"), ("الفائض (ريال)", "num")],
                   [[esc(a), fmt_int(b), fmt_int(c), fmt_int(d)] for a, b, c, d in rows]))
        if res["detail"].empty:
            note("لم تُختر أي فرصة بعد.", "info")
        else:
            section("الفرص المحتسبة في السيناريو الحالي")
            rws = []
            for r in res["detail"].sort_values("in_year", ascending=False).itertuples():
                rws.append([f"<b>{esc(r.opp_id)}</b>", tag("متكرر") if r.nature == "recurring" else tag("لمرة واحدة", "gold"), fmt_int(r.base_in_year), fmt_int(r.in_year) + (" ⟂" if r.capped else "")])
            html(table([("المعرف", ""), ("الطبيعة", ""), ("أساسي (ريال)", "num"), ("في السيناريو (ريال)", "num")], rws))
            st.caption("⟂ = طُبّق السقف المنطقي (إشغال كامل، سقف تعاقدي/مرجعي، أو الرصيد المستحق).")
