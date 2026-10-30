"""مكونات HTML قابلة لإعادة الاستخدام (بطاقات، شارات، جداول) — كلها نصوص HTML تُعرض عبر st.html."""
from __future__ import annotations

import base64
import math
import re
from pathlib import Path

import streamlit as st

from core.config import LOGO_DIR, STATUS_META
from core.formatting import esc, fmt_m, fmt_pct, fmt_points, fmt_sar

ARABIC_RE = re.compile(r"[؀-ۿ]")


DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
PCT_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?%)")


def rich(s) -> str:
    """تهريب HTML مع عزل التواريخ ISO والنسب المئوية حتى لا ينعكس ترتيبها داخل الجمل العربية."""
    out = DATE_RE.sub(r'<bdi dir="ltr">\1</bdi>', esc(s))
    return PCT_RE.sub(r'<bdi dir="ltr">\1</bdi>', out)


def html(s: str):
    st.html(s)


def section(title: str, sub: str = ""):
    html(f'<div class="sec"><h3>{esc(title)}</h3>{f"<span>{esc(sub)}</span>" if sub else ""}</div>')


def kpi(label: str, value: str, sub: str = "", tone: str = "", title: str = "") -> str:
    t = f' title="{esc(title)}"' if title else ""
    return (f'<div class="kpi {tone}"{t}><div class="lbl">{esc(label)}</div>'
            f'<div class="val">{value}</div>{f"<div class=sub>{sub}</div>" if sub else ""}</div>')


def kpi_money(label: str, amount: float, tone: str = "", extra: str = "") -> str:
    """القيمة مختصرة بالمليون، والقيمة الدقيقة ظاهرة تحتها (تعمل على الجوال دون تمرير مؤشر)."""
    num, unit = money_parts(amount)
    val = f"{esc(num)}<small>{esc(unit)}</small>"
    sub = "القيمة الدقيقة: " + esc(fmt_sar(amount)) + (f"<br>{extra}" if extra else "")
    return kpi(label, val, sub, tone, title=fmt_sar(amount))


def money_parts(amount: float) -> tuple[str, str]:
    a = abs(float(amount))
    if a >= 1_000_000:
        return f"{amount / 1_000_000:,.1f}", "مليون ريال"
    if a >= 1_000:
        return f"{amount / 1_000:,.0f}", "ألف ريال"
    return f"{amount:,.0f}", "ريال"


def kpi_grid(cards: list[str]):
    html('<div class="kpi-grid">' + "".join(cards) + "</div>")


def note(text_html: str, kind: str = "info"):
    html(f'<div class="note {kind}">{text_html}</div>')


def pill(status: str) -> str:
    m = STATUS_META[status]
    return f'<span class="pill s-{status}"><i></i>{esc(m["label"])}</span>'


def tag(text: str, kind: str = "") -> str:
    return f'<span class="tag {kind}">{esc(text)}</span>'


def calc_block(text: str) -> str:
    """أسطر عربية تشرح المعادلة، وأسطر المعادلات الرقمية تُعرض من اليسار لليمين."""
    out = []
    for line in str(text).split("\n"):
        if not line.strip():
            continue
        cls = "ar" if ARABIC_RE.search(line) else "math"
        out.append(f'<div class="{cls}">{rich(line)}</div>')
    return '<div class="calc">' + "".join(out) + "</div>"


def table(columns: list, rows: list, row_classes: list | None = None) -> str:
    """columns: [(العنوان، الصنف css)]؛ rows: قوائم من HTML جاهز."""
    head = "".join(f'<th class="{c}">{esc(t)}</th>' for t, c in columns)
    body = []
    for i, r in enumerate(rows):
        rc = (row_classes or [""] * len(rows))[i]
        tds = "".join(f'<td class="{columns[j][1]}">{v}</td>' for j, v in enumerate(r))
        body.append(f'<tr class="{rc}">{tds}</tr>')
    return f'<div class="tbl-wrap"><table class="gt"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def ring(score, status: str) -> str:
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return '<div class="ring empty"><span>—</span></div>'
    color = {"good": "#2E9B4F", "medium": "#E2A72E", "intervene": "#D2463B"}.get(status, "#9AA1AB")
    return f'<div class="ring" style="--p:{max(0, min(100, score)):.1f};--c:{color}"><span>{score:.1f}%</span></div>'


def delta_html(delta, note_txt: str) -> str:
    if delta is None or (isinstance(delta, float) and math.isnan(delta)):
        return f'<span class="na">{esc(note_txt)}</span>'
    cls = "delta-up" if delta >= 0.05 else ("delta-down" if delta <= -0.05 else "delta-flat")
    arrow = "▲" if delta >= 0.05 else ("▼" if delta <= -0.05 else "■")
    return f'<span class="{cls}">{arrow} {esc(fmt_points(delta))}</span> <span class="na">({esc(note_txt)})</span>'


def dept_card(r) -> str:
    unmet = "".join(tag(u, "gray") for u in r["unmet"]) or '<span class="na">لا يوجد</span>'
    if r["status"] == "incomplete":
        unmet_line = ""
    else:
        unmet_line = f'<div class="dstats"><span class="na">مؤشرات لم تحقق مستهدفها:</span> {unmet}</div>'
    return (
        f'<div class="dcard s-{r["status"]}">'
        f'<div class="dtop"><div class="dname">{esc(r["dept_name"])}<small>المعرف الثابت: {esc(r["dept_id"])}</small></div>{pill(r["status"])}</div>'
        f'<div class="dmid">{ring(r["score"], r["status"])}<div class="dstats">'
        f'<div>درجة الأداء: <b>{"—" if r["score"] is None or r["score"] != r["score"] else rich(fmt_pct(r["score"]))}</b></div>'
        f'<div>التغير: {delta_html(r["delta"], r["compare_note"])}</div></div></div>'
        f'{unmet_line}'
        f'<div class="dreason"><b>سبب التصنيف:</b> {rich(r["reason"])}</div>'
        f"</div>"
    )


@st.cache_data(show_spinner=False)
def logo_data_uri() -> str | None:
    """الشعار الرسمي يُقرأ من assets/logo فقط (لا يُرسم أو يُخترع أي شعار)."""
    for name, mime in (("hail_logo.svg", "image/svg+xml"), ("hail_logo.png", "image/png"), ("hail_logo.jpg", "image/jpeg"), ("hail_logo.webp", "image/webp")):
        p = Path(LOGO_DIR) / name
        if p.exists():
            return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
    return None
