"""يولّد docs/DATA_DICTIONARY.md من مخططات الجداول (مصدر واحد للحقيقة مع التحقق في الاستيراد)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.schemas import PERF_TABLES, REVENUE_TABLES, SETTINGS_KEYS  # noqa: E402

KIND = {"str": "نص", "float": "رقم", "int": "عدد صحيح", "bool": "true/false", "date": "تاريخ YYYY-MM-DD", "month": "شهر YYYY-MM", "label": "synthetic / real"}


def table_md(key, t):
    out = [f"### {t.title} — `{key}`", "", t.desc, ""]
    if t.id_cols:
        out.append(f"المفتاح الفريد: `{' + '.join(t.id_cols)}`")
    if t.fks:
        out.append("المراجع: " + "، ".join(f"`{f.col}` → `{f.table}.{f.ref_col}`" for f in t.fks))
    out += ["", "| العمود | النوع | الوصف | القيود |", "|---|---|---|---|"]
    for c in t.columns:
        cons = []
        if c.min is not None:
            cons.append("أكبر من صفر" if 0 < c.min < 1e-3 else f"≥ {c.min:g}")
        if c.max is not None:
            cons.append(f"≤ {c.max:g}")
        if c.choices:
            cons.append("القيم: " + "، ".join(c.choices))
        cons.append("يقبل الفراغ" if c.nullable else "مطلوب")
        out.append(f"| `{c.name}` | {KIND[c.kind]} | {c.desc} | {' · '.join(cons)} |")
    return "\n".join(out) + "\n"


def main():
    md = ["# قاموس البيانات", "", "> Synthetic Data — بيانات تجريبية لا تمثل أرقام أمانة منطقة حائل.", "",
          "يُولَّد هذا الملف آليًا من `core/schemas.py`، وهي نفس المخططات التي يستخدمها التحقق عند الاستيراد.", "",
          "## قواعد عامة", "",
          "- كل جدول يحمل عمود `data_label` بقيمة `synthetic` أو `real`، ولا يُسمح بالخلط داخل الجدول أو المجموعة.",
          "- النسخة المنشورة (وضع العرض) تقبل `synthetic` فقط.",
          "- عند أي خطأ في الاستيراد لا تُستبدل أي بيانات (استبدال ذري للمجموعة كاملة).",
          "- الخلية الفارغة في نتائج الأداء تعني «غير مدخل» ولا تُعامل كصفر.", "",
          "## بيانات الإيرادات", "", "ملف Excel واحد بأوراق بالأسماء التالية، أو ملفات CSV بنفس الأسماء.", ""]
    for k, t in REVENUE_TABLES.items():
        md.append(table_md(k, t))
        if k == "settings":
            md += ["مفاتيح الإعدادات:", "", "| المفتاح | الوصف |", "|---|---|"] + [f"| `{a}` | {b} |" for a, b in SETTINGS_KEYS.items()] + [""]
    md += ["## بيانات الأداء", ""]
    for k, t in PERF_TABLES.items():
        md.append(table_md(k, t))
    (ROOT / "docs" / "DATA_DICTIONARY.md").write_text("\n".join(md), encoding="utf-8")
    print("docs/DATA_DICTIONARY.md")


if __name__ == "__main__":
    main()
