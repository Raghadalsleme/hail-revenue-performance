"""لوحة الإيرادات: المستهدف، المحقق، الفجوة، نسبة التحقيق، المصادر، ومساهمة الفرص المختارة."""
from __future__ import annotations

import streamlit as st

from core.config import SCENARIOS_DEFAULT
from core.formatting import date_ar, esc, fmt_int, fmt_pct, fmt_sar
from core.revenue import compute_kpis, scenario_result, sources_table

from .. import charts
from ..components import html, kpi, kpi_grid, kpi_money, note, section, table
from ..state import opportunities, ss


def render():
    data = ss.rev_data
    s = data.settings
    k = compute_kpis(data)
    opps, _ = opportunities()
    sc = ss.scenario
    mult = ss.multipliers[sc]
    res = scenario_result(opps, ss.selection, mult, k, s.financial_basis)

    att = "غير قابلة للحساب" if k["attainment_pct"] is None else fmt_pct(k["attainment_pct"])
    att_sub = "المستهدف صفر" if k["attainment_pct"] is None else f"المتوقع بنهاية السنة قبل الفرص: {fmt_pct(k['projected_attainment_pct'])}"
    cards = [
        kpi_money("المستهدف السنوي", k["target"], "primary"),
        kpi_money(f"المحقق حتى {date_ar(s.snapshot_date)}", k["realized"], "ok"),
        kpi_money("الفجوة حتى تاريخ اللقطة", k["gap_to_date"], "alert") if k["surplus_to_date"] == 0 else kpi_money("فائض حتى تاريخ اللقطة", k["surplus_to_date"], "ok"),
        kpi("نسبة تحقيق المستهدف", esc(att), esc(att_sub), "neutral"),
        kpi_money("الفجوة المتوقعة بنهاية السنة قبل الفرص", k["projected_gap"], "gold", extra=f"بعد احتساب إيراد أساسي متوقع {esc(fmt_sar(k['baseline_remaining']))}"),
    ]
    kpi_grid(cards)
    note(
        f"<b>الأساس المالي:</b> {esc(s.basis_label)}. <b>تاريخ اللقطة:</b> {esc(date_ar(s.snapshot_date))} — المتبقي من السنة {k['remaining_days']} يومًا. "
        f"<b>الإيراد الأساسي المتوقع</b> هو ما يُتوقع تحصيله أصلًا من المصادر والعقود القائمة دون أي فرص جديدة، ولذلك تُقارن الفرص بالفجوة المتوقعة بنهاية السنة لا بالفجوة حتى اللقطة. "
        f"<b>مصدر البيانات:</b> {esc(s.source_note)}",
        "info",
    )

    c1, c2 = st.columns([1.05, 1], gap="medium")
    with c1:
        with st.container(key="card_sources"):
            html('<div class="card-title">المحقق مقابل المستهدف حسب مصدر الإيراد</div><div class="card-sub">العمود الرمادي = المستهدف السنوي، الأخضر = المحقق حتى تاريخ اللقطة، والنسبة = نسبة التحقيق. مرّر المؤشر لرؤية القيمة الدقيقة.</div>')
            charts.show(charts.sources_vs_target(data.sources), "rev_sources")
    with c2:
        with st.container(key="card_waterfall"):
            html(f'<div class="card-title">مساهمة الفرص المختارة في تقليص الفجوة</div><div class="card-sub">سيناريو «{SCENARIOS_DEFAULT[sc]["label"]}» ({mult:.0%}) — {len(res["selection"].kept)} فرصة مختارة من صفحة السيناريوهات. الخط الذهبي = المستهدف. المحوران يبدآن من الصفر.</div>')
            charts.show(charts.gap_bars(k, res["recurring_in_year"], res["one_time_in_year"], s.financial_basis), "rev_gapbars")

    cards = [
        kpi_money("إيراد متكرر خلال السنة من الفرص المختارة", res["recurring_in_year"], "ok"),
        kpi_money("تحصيل لمرة واحدة خلال السنة", res["one_time_in_year"], "neutral",
                  extra=("يُحتسب على الأساس النقدي" if s.financial_basis == "cash" else "أثر نقدي فقط — لا يُحتسب على أساس الاستحقاق")),
        kpi_money("الفجوة المتبقية بعد الفرص", res["remaining_gap"], "alert" if res["remaining_gap"] > 0 else "ok"),
        kpi_money("الفائض المتوقع", res["surplus"], "ok" if res["surplus"] > 0 else "neutral"),
    ]
    kpi_grid(cards)
    if res["remaining_gap"] > 0:
        note(f"<b>الفرص المختارة لا تكفي لسد الفجوة المتوقعة.</b> يتبقى {esc(fmt_sar(res['remaining_gap']))} بعد احتساب الفرص الممكنة خلال الأيام المتبقية من السنة. "
             "الإيراد السنوي الكامل لبعض الفرص أعلى بكثير لكنه يتحقق في السنة القادمة بسبب مهلة التنفيذ وتواريخ التجديد.", "warn")

    section("تفاصيل مصادر الإيرادات", "القيم الدقيقة بالريال السعودي")
    df = sources_table(data)
    rows = []
    for r in df.sort_values("annual_target_sar", ascending=False).itertuples():
        a = r.attainment_pct
        bar = f'<div class="bar"><i style="width:{min(100, a or 0):.1f}%"></i></div>' if a is not None else ""
        rows.append([f"{esc(r.source_name)}<div class='muted'>{esc(r.source_id)} · {esc(r.category)}</div>", fmt_int(r.annual_target_sar), fmt_int(r.realized_to_date_sar),
                     f"{fmt_pct(a) if a is not None else '—'}{bar}", fmt_int(r.expected_remaining_sar), fmt_int(r.projected_sar), fmt_int(r.projected_gap_sar)])
    rows.append(["الإجمالي (مجموع المصادر)", fmt_int(df["annual_target_sar"].sum()), fmt_int(df["realized_to_date_sar"].sum()),
                 fmt_pct(df["realized_to_date_sar"].sum() / df["annual_target_sar"].sum() * 100) if df["annual_target_sar"].sum() else "—",
                 fmt_int(df["expected_remaining_sar"].sum()), fmt_int(df["projected_sar"].sum()), fmt_int(df["projected_gap_sar"].sum())])
    html(table([("المصدر", ""), ("المستهدف (ريال)", "num"), ("المحقق حتى اللقطة (ريال)", "num"), ("نسبة التحقيق", "num"), ("المتوقع أصلًا لبقية السنة (ريال)", "num"),
                ("المتوقع بنهاية السنة (ريال)", "num"), ("الفجوة المتوقعة للمصدر (ريال)", "num")], rows, [""] * (len(rows) - 1) + ["total"]))
    note("مجموع فجوات المصادر قد يختلف عن الفجوة الكلية لأن المصادر التي تتجاوز مستهدفها لا تُعوض فجوات غيرها في هذا الجدول، بينما تُحسب الفجوة الكلية على المجموع.", "info")
