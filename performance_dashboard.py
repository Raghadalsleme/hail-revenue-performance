"""لوحة متابعة أداء الأقسام لمدير الإدارة العامة."""
from __future__ import annotations

import streamlit as st

from core.config import STATUS_META
from core.formatting import esc, fmt_pct, fmt_points, month_label
from core.performance import PerfSettings, gd_kpis, month_summary, months_range, trend

from .. import charts
from ..components import dept_card, html, kpi, kpi_grid, note, pill, rich, section, table, tag
from ..state import ss


def gd_month_pickers(prefix: str):
    perf = ss.perf
    gds = perf.gds[perf.gds["active"].astype(bool)]
    names = dict(zip(gds["gd_id"], gds["gd_name"]))
    c1, c2, c3 = st.columns([1.3, 1, 1.2])
    gd = c1.selectbox("الإدارة العامة", list(names), format_func=lambda g: names[g], key=f"{prefix}_gd")
    months = months_range(perf, gd)
    if not months:
        c2.selectbox("شهر المتابعة", ["—"], disabled=True, key=f"{prefix}_month_empty")
        return gd, None, c3
    month = c2.selectbox("شهر المتابعة", list(reversed(months)), format_func=month_label, key=f"{prefix}_month_{gd}")
    return gd, month, c3


def _settings_editor():
    perf, s = ss.perf, ss.perf_settings
    with st.expander("الأوزان وحدود التصنيف (إعدادات تجريبية تحتاج اعتماد الإدارة)"):
        cols = st.columns(len(perf.kpis) + 2)
        w = {}
        for i, r in enumerate(perf.kpis.itertuples()):
            w[r.kpi_id] = float(cols[i].number_input(f"وزن {r.kpi_name} %", 0, 100, int(s.weights.get(r.kpi_id, 0)), 5, key=f"pw_{r.kpi_id}"))
        g = float(cols[-2].number_input("حد «جيد» %", 1, 100, int(s.green), 1, key="th_g"))
        y = float(cols[-1].number_input("حد «متوسط» %", 1, 100, int(s.yellow), 1, key="th_y"))
        cand = PerfSettings(weights=w, green=g, yellow=y)
        errs = cand.validate()
        if errs:
            for e in errs:
                st.error(e + " — لم تُطبّق التعديلات.")
        elif cand != s:
            ss.perf_settings = cand
            st.rerun()
        st.caption("التصنيف: جيد ≥ حد «جيد»، متوسط من حد «متوسط» إلى أقل من حد «جيد»، يحتاج تدخل أقل من حد «متوسط»، وبيانات ناقصة عند نقص أي مدخل لمؤشر وزنه أكبر من صفر.")


def render():
    perf = ss.perf
    _settings_editor()
    s = ss.perf_settings
    gd, month, c3 = gd_month_pickers("pd")
    with c3:
        html(f'<div class="note info" style="margin-top:26px;padding:7px 12px">الأوزان: {rich("، ".join(f"{r.kpi_name} {s.weights.get(r.kpi_id, 0):g}%" for r in perf.kpis.itertuples()))}</div>')
    if month is None:
        note("لا توجد بيانات أداء لهذه الإدارة العامة بعد. أضف بيانات شهر من صفحة «إدخال بيانات الأداء».", "warn")
        return
    sm = month_summary(perf, gd, month, s)
    if sm.empty:
        note("لا توجد أقسام فعالة تابعة لهذه الإدارة العامة.", "warn")
        return
    k = gd_kpis(sm)
    kpi_grid([
        kpi("الأقسام التابعة", f"{k['n_depts']}", f"جيد {k['n_good']} · متوسط {k['n_medium']} · يحتاج تدخل {k['n_intervene']}", "primary"),
        kpi("متوسط الأداء", "—" if k["avg_score"] is None else fmt_pct(k["avg_score"]), f"للأقسام المكتملة بياناتها فقط ({k['n_complete']})", "ok"),
        kpi("تحتاج تدخلًا", f"{k['n_intervene']}", f"درجة أقل من {s.yellow:g}%", "alert" if k["n_intervene"] else "neutral"),
        kpi("اكتمال إدخال البيانات", f"{k['n_complete']} من {k['n_depts']}", "—" if k["complete_pct"] is None else f"{k['complete_pct']:.0f}% أكملت بياناتها — الناقص لا يُصنف ضعيفًا", "gold"),
    ])
    html('<div class="note info">'
         f'{pill("good")} {rich(f"{s.green:g}%")} فأعلى &nbsp; {pill("medium")} من {rich(f"{s.yellow:g}%")} إلى أقل من {rich(f"{s.green:g}%")} &nbsp; {pill("intervene")} أقل من {rich(f"{s.yellow:g}%")} &nbsp; {pill("incomplete")} نقص أي مدخل مطلوب'
         '<br>تحقيق كل مؤشر = المحقق ÷ المستهدف × 100 <b>بسقف 100%</b>، فلا يعوض تجاوز مستهدف ضعف مؤشر آخر. القيمة غير المدخلة لا تُعامل كصفر. '
         'هذه لوحة لمتابعة أداء الأقسام وليست نظامًا لاتخاذ قرارات أو جزاءات بحق الموظفين.</div>')

    section(f"بطاقات الأقسام — {month_label(month)}", f"المقارنة مع الشهر التقويمي السابق ({month_label(sm.iloc[0]['prev_month'])}) عند توفر بياناته")
    html('<div class="dgrid">' + "".join(dept_card(r) for _, r in sm.iterrows()) + "</div>")

    follow = sm[sm["status"].isin(["intervene", "incomplete"]) | (sm["delta"].fillna(0) <= -5)]
    section("أقسام تحتاج متابعة", "يحتاج تدخل، أو بيانات ناقصة، أو تراجع 5 نقاط فأكثر")
    if follow.empty:
        note("لا توجد أقسام تحتاج متابعة هذا الشهر.", "ok")
    else:
        rows = []
        for r in follow.itertuples():
            why = []
            if r.status == "intervene":
                why.append("درجة أقل من حد التدخل")
            if r.status == "incomplete":
                why.append("استكمال إدخال البيانات")
            if r.delta is not None and r.delta == r.delta and r.delta <= -5:
                why.append(f"تراجع {fmt_points(r.delta)}")
            rows.append([f"<b>{esc(r.dept_name)}</b>", pill(r.status), esc("، ".join(why)), esc(r.reason)])
        html(table([("القسم", ""), ("الحالة", ""), ("سبب المتابعة", ""), ("التفاصيل", "")], rows))

    t = trend(perf, gd, s)
    c1, c2 = st.columns([1.15, 1], gap="medium")
    with c1:
        with st.container(key="card_trend"):
            html('<div class="card-title">اتجاه درجة الأداء عبر الأشهر</div><div class="card-sub">الشهر غير المكتمل يظهر فراغًا ولا يُوصل بخط. اضغط اسم القسم في المفتاح لإخفائه أو إظهاره.</div>')
            charts.show(charts.perf_trend(t, thresholds=(s.green, s.yellow)), f"trend_{gd}")
    with c2:
        with st.container(key="card_heat"):
            html('<div class="card-title">خريطة الحالة الشهرية</div><div class="card-sub">الرقم = الدرجة، و«ناقص» عند نقص مدخل، و«—» عند عدم وجود بيانات للشهر.</div>')
            charts.show(charts.status_heatmap(t, s), f"heat_{gd}")

    section("جدول مقارنة الأقسام")
    kp = list(perf.kpis.itertuples())
    rows = []
    for r in sm.itertuples():
        cells = [f"<b>{esc(r.dept_name)}</b><div class='muted'>{esc(r.dept_id)}</div>", "—" if r.score is None or r.score != r.score else fmt_pct(r.score), pill(r.status)]
        for kk in kp:
            x = next(d for d in r.details if d["kpi_id"] == kk.kpi_id)
            cells.append("<span class='muted'>غير مدخل</span>" if x["achievement"] is None else fmt_pct(x["achievement"]))
        cells.append(fmt_points(r.delta) if r.delta is not None and r.delta == r.delta else f"<span class='muted'>{esc(r.compare_note)}</span>")
        rows.append(cells)
    html(table([("القسم", ""), ("الدرجة", "num"), ("الحالة", "")] + [(f"تحقيق {kk.kpi_name}", "num") for kk in kp] + [("التغير", "")], rows))

    section("تفاصيل مؤشرات قسم")
    names = dict(zip(sm["dept_id"], sm["dept_name"]))
    did = st.selectbox("اختر القسم", list(names), format_func=lambda d: names[d], key=f"pd_dept_{gd}")
    r = sm.set_index("dept_id").loc[did]
    rows = []
    for x in r["details"]:
        rows.append([f"<b>{esc(x['kpi_name'])}</b><div class='muted'>{esc(x['definition'])}</div>", esc(x["unit"]), f"{x['weight']:g}%",
                     "<span class='muted'>غير مدخل</span>" if x["target"] is None else f"{x['target']:g}",
                     "<span class='muted'>غير مدخل</span>" if x["actual"] is None else f"{x['actual']:g}",
                     "—" if x["raw_ratio"] is None else fmt_pct(x["raw_ratio"]),
                     "—" if x["achievement"] is None else fmt_pct(x["achievement"]),
                     "—" if x["weighted"] is None else f"{x['weighted']:.2f}",
                     tag("حقق", "") if x["met"] else (tag("لم يحقق", "gold") if x["actual"] is not None else tag("غير مدخل", "gray"))])
    html(table([("المؤشر والتعريف", ""), ("الوحدة", "c"), ("الوزن", "c"), ("المستهدف", "num"), ("المحقق", "num"), ("المحقق ÷ المستهدف", "num"),
                ("التحقيق (بسقف 100%)", "num"), ("المساهمة في الدرجة", "num"), ("", "")], rows))
    status = r["status"]
    note(f"{pill(status)} &nbsp; <b>{esc(r['reason'])}</b> — {esc(r['compare_note'])}", {"good": "ok", "medium": "warn", "intervene": "bad", "incomplete": "info"}[status])
    hist = t[t["dept_id"] == did]
    rows = [[esc(month_label(h.month)), "—" if h.score is None or h.score != h.score else fmt_pct(h.score), pill(h.status)] for h in hist.sort_values("month", ascending=False).itertuples()]
    with st.expander(f"سجل القسم الشهري ({len(rows)} شهرًا)"):
        html(table([("الشهر", ""), ("الدرجة", "num"), ("الحالة", "")], rows))
