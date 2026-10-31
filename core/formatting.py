"""تنسيق الأرقام والتواريخ للعرض العربي (أرقام غربية كما هو شائع في اللوحات الحكومية)."""
from __future__ import annotations

import math
from datetime import date

AR_MONTHS = [
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]


def _is_missing(x) -> bool:
    if x is None:
        return True
    try:
        return math.isnan(float(x))
    except (TypeError, ValueError):
        return True


def fmt_int(x) -> str:
    if _is_missing(x):
        return "—"
    return f"{float(x):,.0f}"


def fmt_sar(x, decimals: int = 0) -> str:
    """قيمة دقيقة بالريال: 20,000,000 ريال"""
    if _is_missing(x):
        return "—"
    return f"{float(x):,.{decimals}f} ريال"


def fmt_m(x, decimals: int = 1, unit: bool = True) -> str:
    """قيمة مختصرة: بالمليون إذا تجاوزت مليونًا، وإلا بالألف."""
    if _is_missing(x):
        return "—"
    v = float(x)
    a = abs(v)
    if a >= 1_000_000:
        s = f"{v / 1_000_000:,.{decimals}f}"
        return f"{s} مليون ريال" if unit else f"{s} م"
    if a >= 1_000:
        s = f"{v / 1_000:,.0f}"
        return f"{s} ألف ريال" if unit else f"{s} ألف"
    return f"{v:,.0f} ريال" if unit else f"{v:,.0f}"


def fmt_pct(x, decimals: int = 1) -> str:
    if _is_missing(x):
        return "—"
    return f"{float(x):.{decimals}f}%"


def fmt_points(x, decimals: int = 1) -> str:
    """تغير بالنقاط المئوية بصيغة لفظية (تتجنب انعكاس الإشارة في النص العربي)."""
    if _is_missing(x):
        return "—"
    v = float(x)
    if abs(v) < 0.05:
        return "دون تغير"
    return f"{'ارتفاع' if v > 0 else 'انخفاض'} {abs(v):.{decimals}f} نقطة"


def month_label(month: str) -> str:
    """'2026-09' -> 'سبتمبر 2026'"""
    try:
        y, m = month.split("-")
        return f"{AR_MONTHS[int(m) - 1]} {y}"
    except Exception:  # noqa: BLE001
        return str(month)


def date_ar(d: date) -> str:
    if d is None:
        return "—"
    return f"{d.day} {AR_MONTHS[d.month - 1]} {d.year}"


def esc(s) -> str:
    """تهريب HTML بسيط للنصوص القادمة من البيانات."""
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
