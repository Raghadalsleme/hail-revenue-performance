"""رسوم Plotly بتنسيق موحد: خط عربي، شبكة خافتة، تسميات غير متداخلة، ولا أزرار شكلية."""
from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.config import BRAND, SERIES_COLORS, STATUS_FILL, STATUS_META
from core.formatting import fmt_sar, month_label

FONT = "IBM Plex Sans Arabic, system-ui, sans-serif"
CONFIG = {"displayModeBar": False, "responsive": True, "scrollZoom": False}


def base_layout(fig: go.Figure, height: int = 360, legend: bool = True, margin=None):
    fig.update_layout(
        height=height,
        font=dict(family=FONT, size=13, color=BRAND["ink"]),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=margin or dict(l=10, r=10, t=10, b=10),
        hoverlabel=dict(font=dict(family=FONT, size=13), bgcolor="#FFFFFF", bordercolor=BRAND["line"], align="right"),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=12.5), traceorder="normal"),
        separators=".,",
    )
    fig.update_xaxes(gridcolor="#EEF1EF", zerolinecolor="#D5DCD8", linecolor="#D5DCD8", tickfont=dict(size=12, color=BRAND["muted"]))
    fig.update_yaxes(gridcolor="#EEF1EF", zerolinecolor="#D5DCD8", linecolor="#D5DCD8", tickfont=dict(size=12.5, color=BRAND["ink"]))
    return fig


def show(fig: go.Figure, key: str):
    st.plotly_chart(fig, width="stretch", config=CONFIG, key=key)


def m(x):
    return x / 1_000_000


def sources_vs_target(df: pd.DataFrame) -> go.Figure:
    """المحقق مقابل المستهدف حسب المصدر — أعمدة أفقية، التسميات على اليمين والأعمدة تمتد لليسار."""
    d = df.sort_values("annual_target_sar", ascending=True)
    names = d["source_name"].tolist()
    fig = go.Figure()
    fig.add_bar(y=names, x=m(d["annual_target_sar"]), orientation="h", name="المستهدف السنوي", marker_color=BRAND["target_gray"],
                width=0.72, customdata=d["annual_target_sar"].map(fmt_sar), hovertemplate="%{y}<br>المستهدف: %{customdata}<extra></extra>")
    att = d.apply(lambda r: r["realized_to_date_sar"] / r["annual_target_sar"] * 100 if r["annual_target_sar"] else float("nan"), axis=1)
    fig.add_bar(y=names, x=m(d["realized_to_date_sar"]), orientation="h", name="المحقق حتى تاريخ اللقطة", marker_color=BRAND["green_600"],
                width=0.38, customdata=list(zip(d["realized_to_date_sar"].map(fmt_sar), att.map(lambda v: "—" if math.isnan(v) else f"{v:.1f}%"))),
                hovertemplate="%{y}<br>المحقق: %{customdata[0]}<br>نسبة التحقيق: %{customdata[1]}<extra></extra>")
    fig.add_scatter(y=names, x=m(d["annual_target_sar"]), mode="text", text=att.map(lambda v: "" if math.isnan(v) else f"  {v:.0f}%  "),
                    textposition="middle left", textfont=dict(size=12, color=BRAND["muted"]), showlegend=False, hoverinfo="skip")
    base_layout(fig, height=max(320, 40 * len(d) + 80), margin=dict(l=10, r=10, t=36, b=36))
    xmax = m(d["annual_target_sar"].max()) * 1.18 if len(d) else 1
    fig.update_layout(barmode="overlay", bargap=0.25)
    fig.update_xaxes(autorange=False, range=[xmax, 0], title=dict(text="مليون ريال", font=dict(size=12, color=BRAND["muted"])), ticksuffix="")
    fig.update_yaxes(side="right", automargin=True, ticks="", ticklabelstandoff=8)
    return fig


def gap_bars(k: dict, recurring: float, one_time: float, basis: str) -> go.Figure:
    """شريطان يبدآن من الصفر (دون محور مقتطع):
    1) تكوين المستهدف السنوي: المحقق + الأساسي المتوقع + الفرص المختارة + الفجوة المتبقية.
    2) تكبير للفجوة المتوقعة: ما تغطيه الفرص المتكررة وتحصيل المرة الواحدة وما يتبقى."""
    from plotly.subplots import make_subplots
    counted_one = one_time if basis == "cash" else 0.0
    opps = recurring + counted_one
    total = k["realized"] + k["baseline_remaining"] + opps
    remaining = max(0.0, k["target"] - total)
    surplus = max(0.0, total - k["target"])
    gap = k["projected_gap"]
    rem_gap = max(0.0, gap - opps)
    colors = {"realized": BRAND["green"], "baseline": "#5E9C80", "recurring": "#A9853A", "one_time": "#D9B865", "opps": "#A9853A", "remaining": "#F3D3CF"}
    fig = make_subplots(rows=2, cols=1, vertical_spacing=0.34, row_heights=[0.5, 0.5],
                        subplot_titles=("تكوين المستهدف السنوي (مليون ريال)", f"الفجوة المتوقعة {m(gap):,.2f} مليون: ما تغطيه الفرص المختارة"))
    seen = set()

    def seg(row, label, val, key, scale_total, y):
        show = key not in seen
        seen.add(key)
        txt = f"{m(val):,.2f}" if scale_total and val / scale_total >= 0.07 else ""
        fig.add_bar(y=[y], x=[m(val)], orientation="h", name=label, legendgroup=key, showlegend=show, marker=dict(color=colors[key], line=dict(color="#FFFFFF", width=2)),
                    text=[txt], textposition="inside", insidetextanchor="middle", textfont=dict(size=12.5, color="#FFFFFF" if key in ("realized", "baseline", "recurring") else BRAND["ink"]),
                    customdata=[fmt_sar(val)], hovertemplate=label + ": %{customdata}<extra></extra>", row=row, col=1)

    t1 = max(k["target"], total) or 1
    seg(1, "المحقق حتى اللقطة", k["realized"], "realized", t1, "المستهدف")
    seg(1, "الإيراد الأساسي المتوقع", k["baseline_remaining"], "baseline", t1, "المستهدف")
    seg(1, "فرص متكررة", recurring, "recurring", t1, "المستهدف")
    if basis == "cash":
        seg(1, "تحصيل لمرة واحدة", one_time, "one_time", t1, "المستهدف")
    seg(1, "الفجوة المتبقية", remaining, "remaining", t1, "المستهدف")
    if gap > 0:
        t2 = max(gap, opps) or 1
        seg(2, "فرص متكررة", recurring, "recurring", t2, "الفجوة")
        if basis == "cash":
            seg(2, "تحصيل لمرة واحدة", counted_one, "one_time", t2, "الفجوة")
        seg(2, "الفجوة المتبقية", rem_gap, "remaining", t2, "الفجوة")
        fig.add_vline(x=m(gap), line=dict(color="#B42318", width=1.5, dash="dot"), row=2, col=1)
    fig.add_vline(x=m(k["target"]), line=dict(color=BRAND["gold"], width=2, dash="dash"), row=1, col=1)
    base_layout(fig, height=430, margin=dict(l=10, r=10, t=80, b=20))
    fig.update_layout(barmode="stack", bargap=0.35, legend=dict(y=1.2))
    fig.update_xaxes(autorange="reversed", ticksuffix="")
    fig.update_yaxes(showticklabels=False, showgrid=False)
    for a in fig.layout.annotations:
        a.update(font=dict(size=13, color=BRAND["ink"]), x=1, xanchor="right")
    if surplus > 0:
        fig.add_annotation(xref="x domain", yref="y domain", x=0, y=-0.35, text=f"فائض متوقع {m(surplus):,.2f} مليون", showarrow=False, font=dict(size=12, color="#1F7A3A"), xanchor="left")
    return fig


def scenario_bars(rows: list, projected_gap: float) -> go.Figure:
    """[(اسم السيناريو، المساهمة)] مع خط الفجوة المتوقعة."""
    fig = go.Figure()
    xs = [r[0] for r in rows]
    fig.add_bar(x=xs, y=[m(r[1]) for r in rows], marker_color=["#7FB59B", BRAND["green_600"], BRAND["green"]], width=0.5,
                text=[f"{m(r[1]):,.2f}" for r in rows], textposition="outside", customdata=[fmt_sar(r[1]) for r in rows],
                hovertemplate="%{x}<br>المساهمة: %{customdata}<extra></extra>", showlegend=False)
    if projected_gap > 0:
        fig.add_hline(y=m(projected_gap), line=dict(color="#D2463B", width=2, dash="dash"))
        fig.add_annotation(xref="paper", x=0.01, y=m(projected_gap), text=f"الفجوة المتوقعة {m(projected_gap):,.2f}", showarrow=False, yshift=11,
                           font=dict(size=12, color="#B42318"), xanchor="left")
    base_layout(fig, height=320, legend=False, margin=dict(l=10, r=10, t=30, b=10))
    top = max([m(r[1]) for r in rows] + [m(projected_gap)]) * 1.25 or 1
    fig.update_yaxes(range=[0, top], title=dict(text="مليون ريال", font=dict(size=12, color=BRAND["muted"])), side="right")
    fig.update_xaxes(autorange="reversed")
    return fig


def month_axis(months: list) -> tuple[list, str]:
    """أسماء الأشهر فقط إذا كانت كلها في سنة واحدة (والسنة في عنوان المحور) لتجنب تدوير التسميات."""
    years = {x[:4] for x in months}
    if len(years) == 1:
        from core.formatting import AR_MONTHS
        return [AR_MONTHS[int(x[5:7]) - 1] for x in months], f"سنة {next(iter(years))}"
    return [month_label(x) for x in months], ""


def perf_trend(t: pd.DataFrame, highlight: list | None = None, thresholds=(90, 70)) -> go.Figure:
    """اتجاه الدرجات: الأشهر الناقصة تظهر فراغًا (لا وصل بين النقاط)."""
    fig = go.Figure()
    months = sorted(t["month"].unique())
    labels, ytitle = month_axis(months)
    green, yellow = thresholds
    fig.add_hrect(y0=green, y1=100.5, fillcolor="#E9F4EC", opacity=0.6, line_width=0, layer="below")
    fig.add_hrect(y0=yellow, y1=green, fillcolor="#FBF3E0", opacity=0.6, line_width=0, layer="below")
    fig.add_hrect(y0=0, y1=yellow, fillcolor="#FBECEA", opacity=0.5, line_width=0, layer="below")
    for i, (did, g) in enumerate(t.groupby("dept_id", sort=False)):
        g = g.set_index("month").reindex(months)
        name = g["dept_name"].dropna().iloc[0] if g["dept_name"].notna().any() else did
        visible = True if not highlight else (did in highlight)
        fig.add_scatter(x=labels, y=g["score"], mode="lines+markers", name=name, connectgaps=False,
                        line=dict(width=2, color=SERIES_COLORS[i % len(SERIES_COLORS)]), marker=dict(size=8),
                        visible=True if visible else "legendonly",
                        hovertemplate="%{fullData.name}<br>%{x}: %{y:.1f}%<extra></extra>")
    base_layout(fig, height=380, margin=dict(l=10, r=10, t=40, b=10))
    lo = max(0, min(50, (t["score"].min() if t["score"].notna().any() else 50) - 8))
    fig.update_yaxes(range=[lo, 101], ticksuffix="%", side="right")
    fig.update_xaxes(autorange="reversed", type="category", tickangle=0, title=dict(text=ytitle, font=dict(size=12, color=BRAND["muted"])))
    return fig


def status_heatmap(t: pd.DataFrame, s) -> go.Figure:
    """خريطة الحالة الشهرية: لون الحالة + نص الدرجة أو «ناقص» داخل كل خلية."""
    months = sorted(t["month"].unique())
    depts = list(dict.fromkeys(t["dept_id"]))
    names = [t.loc[t["dept_id"] == d, "dept_name"].iloc[0] for d in depts]
    code = {"intervene": 0, "medium": 1, "good": 2, "incomplete": 3}
    z, txt, hov = [], [], []
    for d in depts:
        g = t[t["dept_id"] == d].set_index("month")
        zr, tr, hr = [], [], []
        for mth in months:
            r = g.loc[mth]
            zr.append(code[r["status"]])
            if r["status"] == "incomplete":
                tr.append("—" if r["no_data"] else "ناقص")
            else:
                tr.append(f"{r['score']:.0f}")
            hr.append(("لا توجد بيانات مدخلة" if r["no_data"] else STATUS_META[r["status"]]["label"]) + ("" if r["status"] == "incomplete" else f" — {r['score']:.1f}%"))
        z.append(zr); txt.append(tr); hov.append(hr)
    light = {"intervene": "#EFA49C", "medium": "#F2D38B", "good": "#9FD3AE", "incomplete": "#DADEE3"}  # تعبئة فاتحة ليبقى النص الداكن مقروءًا
    cs = [[0, light["intervene"]], [0.25, light["intervene"]], [0.25, light["medium"]], [0.5, light["medium"]],
          [0.5, light["good"]], [0.75, light["good"]], [0.75, light["incomplete"]], [1, light["incomplete"]]]
    xl, xtitle = month_axis(months)
    fig = go.Figure(go.Heatmap(z=z, x=xl, y=names, text=txt, texttemplate="%{text}", textfont=dict(size=12.5, color=BRAND["ink"]),
                               customdata=hov, hovertemplate="%{y}<br>%{x}: %{customdata}<extra></extra>", colorscale=cs, zmin=-0.5, zmax=3.5, showscale=False, xgap=3, ygap=3))
    base_layout(fig, height=60 + 46 * len(depts), legend=False, margin=dict(l=10, r=10, t=10, b=10))
    fig.update_xaxes(autorange="reversed", side="top", showgrid=False, tickangle=0, title=dict(text=xtitle, font=dict(size=12, color=BRAND["muted"]), standoff=4))
    fig.update_yaxes(side="right", autorange="reversed", showgrid=False, ticklabelstandoff=8)
    return fig


def gap_simple(k: dict, recurring: float, one_time: float, basis: str) -> go.Figure:
    """شريط واحد يبدأ من الصفر: المحقق + المتوقع أصلًا + الفرص المختارة + المتبقي = المستهدف."""
    counted_one = one_time if basis == "cash" else 0.0
    opps = recurring + counted_one
    remaining = max(0.0, k["target"] - k["realized"] - k["baseline_remaining"] - opps)
    parts = [
        ("المحقق", k["realized"], BRAND["green"], "#FFFFFF"),
        ("متوقع أصلًا", k["baseline_remaining"], "#5E9C80", "#FFFFFF"),
        ("الفرص المختارة", opps, BRAND["gold"], "#FFFFFF"),
        ("المتبقي", remaining, "#F3D3CF", "#B42318"),
    ]
    fig = go.Figure()
    total = sum(p[1] for p in parts) or 1
    for name, v, col, tc in parts:
        fig.add_bar(y=[""], x=[m(v)], orientation="h", name=f"{name} ({m(v):,.1f})", marker=dict(color=col, line=dict(color="#FFFFFF", width=2)),
                    text=[f"{m(v):,.1f}" if v / total >= 0.06 else ""], textposition="inside", insidetextanchor="middle",
                    textfont=dict(size=13, color=tc), customdata=[fmt_sar(v)], hovertemplate=name + ": %{customdata}<extra></extra>")
    fig.add_vline(x=m(k["target"]), line=dict(color=BRAND["gold"], width=2, dash="dash"))
    base_layout(fig, height=170, margin=dict(l=10, r=10, t=0, b=24))
    fig.update_layout(barmode="stack", bargap=0.2, legend=dict(orientation="h", y=-0.35, yanchor="top", x=1, xanchor="right"))
    fig.update_xaxes(autorange="reversed", title=dict(text="مليون ريال", font=dict(size=11.5, color=BRAND["muted"])))
    fig.update_yaxes(showticklabels=False, showgrid=False)
    return fig
