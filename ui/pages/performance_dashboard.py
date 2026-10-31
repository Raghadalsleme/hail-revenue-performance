"""أداء الأقسام: بطاقات الأقسام والاتجاه الشهري."""
from __future__ import annotations

import streamlit as st

from core.formatting import esc, fmt_pct, fmt_points, month_label
from core.performance import PerfSettings, gd_kpis, month_summary, months_range, trend

from .. import charts
from ..components import dept_card, html, kpi, kpi_grid, note, pill, table
from ..state import ss


def gd_month_pickers(prefix: str):
    perf = ss.perf
    gds = perf.gds[perf.gds["active"].astype(bool)]
    names = dict(zip(gds["gd_id"], gds["gd_name"]))
    c1, c2 = st.columns(2)
    gd = c1.selectbox("الإدارة العامة", list(names), format_func=lambda g: names[g], key=f"{prefix}_gd")
    months = months_range(perf, gd)
    if not months:
        c2.selectbox("الشهر", ["—"], disabled=True, key=f"{prefix}_month_empty")
        return gd, None
    month = c2.selectbox("الشهر", list(reversed(months)), format_func=month_label, key=f"{prefix}_month_{gd}")
    return gd, month


def _settings_editor():
    perf, s = ss.perf, ss.perf_settings
    with st.expander("الأوزان وحدود الألوان"):
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
                st.error(e)
        elif cand != s:
            ss.perf_settings = cand
            st.rerun()
        st.caption("تحقيق كل مؤشر = المحقق ÷ المستهدف بحد أقصى 100%، والدرجة = المتوسط المرجح. الحقل الفارغ لا يُعامل كصفر. إعدادات تجريبية للمتابعة فقط، وليست للجزاءات.")


def render():
    perf = ss.perf
    s = ss.perf_settings
    gd, month = gd_month_pickers("pd")
    if month is None:
        note("لا توجد بيانات لهذه الإدارة بعد. أضفها من «إدخال البيانات».", "warn")
        _settings_editor()
        return
    sm = month_summary(perf, gd, month, s)
    if sm.empty:
        note("لا توجد أقسام فعالة في هذه الإدارة.", "warn")
        return
    k = gd_kpis(sm)
    kpi_grid([
        kpi("متوسط الأداء", "—" if k["avg_score"] is None else fmt_pct(k["avg_score"]), "للأقسام المكتملة بياناتها", "primary"),
        kpi("يحتاج تدخل", f"{k['n_intervene']}", f"جيد {k['n_good']} · متوسط {k['n_medium']}", "alert" if k["n_intervene"] else "neutral"),
        kpi("اكتمال البيانات", f"{k['n_complete']} من {k['n_depts']}", "الناقص يظهر بالرمادي", "gold"),
    ])
    follow = sm[sm["status"].isin(["intervene", "incomplete"])]
    if len(follow):
        note("<b>تحتاج متابعة:</b> " + "، ".join(esc(n) for n in follow["dept_name"]), "warn")

    html('<div class="dgrid">' + "".join(dept_card(r, s) for _, r in sm.iterrows()) + "</div>")

    t = trend(perf, gd, s)
    with st.container(key="card_trend"):
        html('<div class="card-title">اتجاه الأداء الشهري</div><div class="card-sub">الشهر غير المكتمل يظهر فراغًا.</div>')
        charts.show(charts.perf_trend(t, thresholds=(s.green, s.yellow)), f"trend_{gd}")

    with st.expander("جدول المقارنة وتفاصيل المؤشرات"):
        rows = []
        for r in sm.itertuples():
            cells = [f"<b>{esc(r.dept_name)}</b>", "—" if r.score is None or r.score != r.score else fmt_pct(r.score), pill(r.status)]
            for x in r.details:
                if x["actual"] is None or x["target"] is None:
                    cells.append("<span class='muted'>غير مدخل</span>")
                else:
                    cells.append(f"{x['actual']:g} / {x['target']:g}")
            cells.append(fmt_points(r.delta) if r.delta is not None and r.delta == r.delta else "—")
            rows.append(cells)
        html(table([("القسم", ""), ("الدرجة", "num"), ("الحالة", "")] +
                   [(f"{x.kpi_name} (محقق/مستهدف)", "num") for x in perf.kpis.itertuples()] + [("التغير", "")], rows))
        st.caption(f"مقارنة {month_label(month)} بالشهر السابق له فقط عند اكتمال بياناته.")

    _settings_editor()
