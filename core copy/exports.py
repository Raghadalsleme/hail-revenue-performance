"""تصدير Excel (اتجاه من اليمين لليسار) لنتائج الإيرادات والأداء والقوالب والنسخ الاحتياطية."""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd

from .config import APP_NAME_AR, APP_VERSION, PROTOTYPE_NOTICE, SYNTHETIC_NOTICE, SCENARIOS_DEFAULT
from .formatting import month_label
from .opportunities import EASE_LABELS, RISK_LABELS
from .schemas import PERF_TABLES, REVENUE_TABLES, SETTINGS_KEYS


def _bool_txt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return v


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
        elif out[c].dtype == object:
            out[c] = out[c].map(_bool_txt)
    return out


class _Book:
    def __init__(self):
        self.buf = io.BytesIO()
        self.w = pd.ExcelWriter(self.buf, engine="xlsxwriter")
        wb = self.w.book
        self.f_head = wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#0E5A43", "border": 1, "border_color": "#C9D3CE", "text_wrap": True, "valign": "vcenter", "align": "center", "font_name": "Arial"})
        self.f_txt = wb.add_format({"text_wrap": True, "valign": "top", "border": 1, "border_color": "#E1E6E3", "font_name": "Arial", "reading_order": 2})
        self.f_num = wb.add_format({"num_format": "#,##0", "valign": "top", "border": 1, "border_color": "#E1E6E3", "font_name": "Arial"})
        self.f_dec = wb.add_format({"num_format": "0.0", "valign": "top", "border": 1, "border_color": "#E1E6E3", "font_name": "Arial"})
        self.f_title = wb.add_format({"bold": True, "font_size": 14, "font_color": "#0E5A43", "font_name": "Arial", "reading_order": 2})
        self.f_note = wb.add_format({"italic": True, "font_color": "#7A5B12", "font_name": "Arial", "text_wrap": True, "reading_order": 2})
        self.f_sel = wb.add_format({"bg_color": "#EAF3EF", "text_wrap": True, "valign": "top", "border": 1, "border_color": "#E1E6E3", "font_name": "Arial", "reading_order": 2})

    def table(self, df: pd.DataFrame, sheet: str, widths: dict | None = None, num_cols=(), dec_cols=(), title: str | None = None, highlight_col: str | None = None, highlight_val=None):
        df = _prep(df)
        start = 3 if title else 0
        df.to_excel(self.w, sheet_name=sheet, index=False, startrow=start)
        ws = self.w.sheets[sheet]
        ws.right_to_left()
        if title:
            ws.write(0, 0, title, self.f_title)
            ws.write(1, 0, f"{SYNTHETIC_NOTICE} — {PROTOTYPE_NOTICE}", self.f_note)
        for j, c in enumerate(df.columns):
            ws.write(start, j, c, self.f_head)
            fmt = self.f_num if c in num_cols else (self.f_dec if c in dec_cols else self.f_txt)
            ws.set_column(j, j, (widths or {}).get(c, max(12, min(45, len(str(c)) + 4))), fmt)
        if highlight_col and highlight_col in df.columns:
            j = list(df.columns).index(highlight_col)
            for i, v in enumerate(df[highlight_col]):
                if v == highlight_val:
                    ws.set_row(start + 1 + i, None, self.f_sel)
                    _ = j
        ws.freeze_panes(start + 1, 0)
        ws.set_row(start, 30)
        return ws

    def kv(self, rows: list, sheet: str, title: str):
        df = pd.DataFrame(rows, columns=["البند", "القيمة"])
        ws = self.table(df, sheet, widths={"البند": 46, "القيمة": 70}, title=title)
        return ws

    def bytes(self) -> bytes:
        self.w.close()
        return self.buf.getvalue()


def _join(x):
    if isinstance(x, (list, tuple)):
        if x and isinstance(x[0], (list, tuple)):
            return "\n".join(f"{a}: {b}" for a, b in x)
        return "\n".join(f"• {i}" for i in x)
    return x


def revenue_excel(data, kpis: dict, opps: pd.DataFrame, excluded: pd.DataFrame, scenario_key: str, multipliers: dict,
                  result: dict, all_results: dict, weights: dict, engine_params: dict) -> bytes:
    b = _Book()
    s = data.settings
    sel = set(result["selection"].kept)
    dropped = dict(result["selection"].dropped)
    det = result["detail"].set_index("opp_id") if not result["detail"].empty else pd.DataFrame()
    sc_label = SCENARIOS_DEFAULT[scenario_key]["label"]
    rows = [
        ("المنصة", f"{APP_NAME_AR} — الإصدار {APP_VERSION}"),
        ("حالة النظام", PROTOTYPE_NOTICE),
        ("وسم البيانات", SYNTHETIC_NOTICE if s.data_label == "synthetic" else "بيانات حقيقية (real)"),
        ("مصدر البيانات", s.source_note),
        ("تاريخ اللقطة (البيانات حتى)", s.snapshot_date.isoformat()),
        ("تاريخ إنشاء التقرير", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("السنة المالية", s.fiscal_year),
        ("الأساس المالي", s.basis_label),
        ("المستهدف السنوي (ريال)", round(kpis["target"], 2)),
        ("المحقق حتى تاريخ اللقطة (ريال)", round(kpis["realized"], 2)),
        ("الفجوة حتى تاريخ اللقطة (ريال)", round(kpis["gap_to_date"], 2)),
        ("نسبة تحقيق المستهدف", "غير قابلة للحساب (المستهدف صفر)" if kpis["attainment_pct"] is None else f"{kpis['attainment_pct']:.2f}%"),
        ("الإيراد الأساسي المتوقع لبقية السنة (ريال)", round(kpis["baseline_remaining"], 2)),
        ("المتوقع بنهاية السنة قبل الفرص (ريال)", round(kpis["projected_year_end"], 2)),
        ("الفجوة المتوقعة بنهاية السنة قبل الفرص (ريال)", round(kpis["projected_gap"], 2)),
        ("السيناريو المختار", f"{sc_label} (معامل {multipliers[scenario_key]:.0%})"),
        ("عدد الفرص المختارة المحتسبة", len(sel)),
        ("إيراد متكرر خلال السنة من الفرص المختارة (ريال)", round(result["recurring_in_year"], 2)),
        ("تحصيل لمرة واحدة خلال السنة (ريال)", round(result["one_time_in_year"], 2)),
        ("المساهمة المحتسبة في سد الفجوة (ريال)", round(result["contribution"], 2)),
        ("الفجوة المتبقية بعد الفرص (ريال)", round(result["remaining_gap"], 2)),
        ("الفائض المتوقع (ريال)", round(result["surplus"], 2)),
        ("تنبيه", "التقديرات تحليلية مبنية على افتراضات وليست حقائق مالية مؤكدة، والاقتراحات ليست موافقة تنظيمية أو إذنًا بالتنفيذ. الإيراد المعروض قبل خصم تكاليف التنفيذ والتشغيل (ليس ربحًا)."),
    ]
    if s.financial_basis != "cash":
        rows.append(("ملاحظة الأساس", "على أساس الاستحقاق لا يُحتسب تحصيل الذمم السابقة إيرادًا جديدًا؛ يظهر كأثر نقدي فقط."))
    b.kv(rows, "الملخص", "ملخص تقرير فرص تنمية الإيرادات")

    out = []
    for o in opps.itertuples():
        if o.opp_id in sel:
            state = "مختارة"
        elif o.opp_id in dropped:
            state = "مستبعدة: " + dropped[o.opp_id]
        else:
            state = "غير مختارة"
        sc_val = float(det.at[o.opp_id, "in_year"]) if o.opp_id in sel else None
        out.append({
            "الترتيب": o.rank, "المعرف": o.opp_id, "الحالة في السيناريو": state, "النوع": o.type_label,
            "المرجع": f"{o.ref_type}: {o.ref_ids}", "العنوان": o.title, "سبب الاقتراح": o.reason, "الطبيعة": o.nature_label,
            "المساهمة الأساسية حتى نهاية السنة": round(o.in_year, 2),
            f"المساهمة في سيناريو {sc_label}": round(sc_val, 2) if sc_val is not None else None,
            "الإيراد السنوي المحتمل (سنة تشغيل كاملة)": round(o.annual_potential, 2),
            "إجمالي التحصيل لمرة واحدة (الحملة كاملة)": round(o.one_time_total, 2),
            "تاريخ بدء الأثر": o.effective_date.isoformat(), "المهلة (يوم)": o.lead_days, "أيام الأثر ضمن السنة": o.in_year_days,
            "السهولة": f"{o.ease} — {EASE_LABELS[o.ease]}", "المخاطر": f"{o.risk} — {RISK_LABELS[o.risk]}",
            "درجة الأولوية (نسبية)": o.priority_score, "طريقة الحساب": o.method, "الافتراضات": _join(o.assumptions),
            "الأدلة": _join(o.evidence), "المراجعات والموافقات المطلوبة": _join(o.approvals), "السقف": o.cap_note,
        })
    odf = pd.DataFrame(out)
    money = [c for c in odf.columns if "المساهمة" in c or "الإيراد" in c or "التحصيل" in c]
    b.table(odf, "الفرص", widths={"العنوان": 40, "سبب الاقتراح": 45, "طريقة الحساب": 60, "الافتراضات": 60, "الأدلة": 55, "المراجعات والموافقات المطلوبة": 50, "الحالة في السيناريو": 28, "المرجع": 30},
            num_cols=money, dec_cols=("درجة الأولوية (نسبية)",), title="الفرص المكتشفة (المختارة مظللة)", highlight_col="الحالة في السيناريو", highlight_val="مختارة")
    b.table(excluded if not excluded.empty else pd.DataFrame([{"المرجع": "—", "النوع": "—", "السبب": "لا توجد عناصر مستبعدة"}]), "المستبعد", widths={"السبب": 90, "المرجع": 18}, title="ما الذي استُبعد ولماذا")

    sc_rows = []
    for k, r in all_results.items():
        sc_rows.append({"السيناريو": SCENARIOS_DEFAULT[k]["label"], "المعامل": f"{multipliers[k]:.0%}", "إيراد متكرر خلال السنة": round(r["recurring_in_year"], 2),
                        "تحصيل لمرة واحدة": round(r["one_time_in_year"], 2), "المساهمة المحتسبة": round(r["contribution"], 2),
                        "الفجوة المتبقية": round(r["remaining_gap"], 2), "الفائض": round(r["surplus"], 2)})
    b.table(pd.DataFrame(sc_rows), "السيناريوهات", num_cols=("إيراد متكرر خلال السنة", "تحصيل لمرة واحدة", "المساهمة المحتسبة", "الفجوة المتبقية", "الفائض"),
            title="مقارنة السيناريوهات لنفس الفرص المختارة (معاملات حساسية افتراضية وليست فواصل ثقة إحصائية)")

    rr = engine_params.get("recovery_rates", {})
    meth = [
        ("معادلة الأولوية", "الدرجة = (و1×مساهمة السنة المعيارية + و2×السهولة المعيارية + و3×عكس المخاطر) ÷ مجموع الأوزان — درجة نسبية وليست احتمال نجاح"),
        ("الأوزان", f"مساهمة السنة {weights['contribution']}% — السهولة {weights['ease']}% — المخاطر {weights['risk']}%"),
        ("معاملات السيناريوهات", "، ".join(f"{SCENARIOS_DEFAULT[k]['label']} {v:.0%}" for k, v in multipliers.items())),
        ("السقوف", "التأجير: إشغال كامل 100%؛ التجديد: الحد الأعلى للنطاق المرجعي أو السقف التعاقدي؛ التحصيل: الرصيد غير المحصل ونسبة استرداد ≤ 100%"),
        ("منع الازدواج", "يُستبعد المسدد سابقًا، ويُطرح الإيراد الأساسي/التحصيل المتوقع أصلًا، والفرص المتعارضة على المرجع نفسه لا تُجمع"),
        ("نسب الاسترداد", "، ".join(f"{k}: {v:.0%}" for k, v in rr.items())),
        ("نافذة التجديد", f"{engine_params.get('renewal_window_days')} يومًا من تاريخ اللقطة؛ حد الانخفاض عن المرجع {engine_params.get('underpricing_threshold', 0):.0%}"),
        ("الذكاء الاصطناعي", "لا يوجد نموذج تعلم آلة مدرب في هذا الإصدار؛ المحرك قواعد تحليلية قابلة للتفسير، والبنية تسمح بإضافة نموذج لاحقًا عند توفر بيانات تاريخية حقيقية"),
    ]
    b.kv(meth, "المنهجية والإعدادات", "المنهجية والإعدادات المستخدمة")
    for key, df in data.tables().items():
        b.table(df, f"مدخلات_{key}"[:31], title=f"المدخلات: {REVENUE_TABLES[key].title}")
    return b.bytes()


def perf_excel(perf, gd_id: str, month: str, settings, summary: pd.DataFrame) -> bytes:
    b = _Book()
    gd_name = perf.gds.set_index("gd_id").at[gd_id, "gd_name"]
    from .performance import gd_kpis
    k = gd_kpis(summary)
    meta = [
        ("الإدارة العامة", f"{gd_name} ({gd_id})"),
        ("الشهر", f"{month_label(month)} ({month})"),
        ("تاريخ التصدير", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("مصدر البيانات", SYNTHETIC_NOTICE if perf.label == "synthetic" else "بيانات مدخلة/مستوردة (real)"),
        ("عدد الأقسام", k["n_depts"]),
        ("متوسط الأداء (للأقسام المكتملة)", "—" if k["avg_score"] is None else round(k["avg_score"], 2)),
        ("أقسام تحتاج تدخلًا", k["n_intervene"]),
        ("اكتمال البيانات", f"{k['n_complete']} من {k['n_depts']}"),
        ("الأوزان", "، ".join(f"{r.kpi_name} {settings.weights.get(r.kpi_id, 0):g}%" for r in perf.kpis.itertuples())),
        ("حدود التصنيف", f"جيد ≥ {settings.green:g}% — متوسط من {settings.yellow:g}% إلى أقل من {settings.green:g}% — يحتاج تدخل < {settings.yellow:g}% — بيانات ناقصة عند نقص أي مدخل مطلوب"),
        ("طريقة الحساب", "تحقيق المؤشر = المحقق ÷ المستهدف × 100 بسقف 100%؛ درجة القسم = المتوسط المرجح؛ تُقرّب لمنزلتين قبل التصنيف"),
        ("تنبيه", "إعدادات تجريبية تحتاج اعتماد الإدارة وليست معايير رسمية للأمانة. لوحة متابعة وليست أداة لاتخاذ قرارات أو جزاءات بحق الموظفين."),
    ]
    b.kv(meta, "الملخص", f"ملخص أداء الأقسام — {month_label(month)}")
    rows = []
    for r in summary.itertuples():
        rows.append({"معرف القسم": r.dept_id, "القسم": r.dept_name, "الدرجة": r.score, "الحالة": r.status_label,
                     "التغير عن الشهر السابق (نقطة)": r.delta, "ملاحظة المقارنة": r.compare_note, "سبب التصنيف": r.reason,
                     "مؤشرات لم تحقق المستهدف": "، ".join(r.unmet) if r.unmet else "—"})
    b.table(pd.DataFrame(rows), "نتائج الأقسام", widths={"سبب التصنيف": 60, "ملاحظة المقارنة": 36, "القسم": 28, "مؤشرات لم تحقق المستهدف": 40}, dec_cols=("الدرجة", "التغير عن الشهر السابق (نقطة)"), title="نتائج الأقسام")
    det = []
    for r in summary.itertuples():
        for x in r.details:
            det.append({"معرف القسم": r.dept_id, "القسم": r.dept_name, "المؤشر": x["kpi_name"], "التعريف": x["definition"], "الوحدة": x["unit"],
                        "الوزن %": x["weight"], "المستهدف": x["target"], "المحقق": x["actual"],
                        "التحقيق % (بسقف 100)": None if x["achievement"] is None else round(x["achievement"], 2),
                        "المساهمة في الدرجة (نقطة)": None if x["weighted"] is None else round(x["weighted"], 2),
                        "حقق المستهدف": "نعم" if x["met"] else ("غير مدخل" if x["actual"] is None or x["target"] is None else "لا")})
    b.table(pd.DataFrame(det), "المؤشرات والمدخلات", widths={"التعريف": 55, "القسم": 26}, dec_cols=("الوزن %", "المستهدف", "المحقق", "التحقيق % (بسقف 100)", "المساهمة في الدرجة (نقطة)"), title="المؤشرات والمستهدفات والمحقق")
    b.table(perf.kpis.rename(columns={"kpi_id": "المعرف", "kpi_name": "المؤشر", "definition": "التعريف", "unit": "الوحدة", "default_weight": "الوزن الافتراضي", "min_value": "أدنى قيمة", "max_value": "أعلى قيمة"}), "تعريف المؤشرات", widths={"التعريف": 70}, title="تعريف المؤشرات")
    return b.bytes()


def perf_backup_excel(perf) -> bytes:
    b = _Book()
    for k, df in perf.tables().items():
        b.table(df, k)
    return b.bytes()


def revenue_template_excel() -> bytes:
    """قالب فارغ بالأعمدة المطلوبة + ورقة تعليمات."""
    b = _Book()
    instr = [("الغرض", "قالب استيراد بيانات الإيرادات: املأ كل ورقة بنفس أسماء الأعمدة، ولا تغيّر أسماء الأوراق.")]
    instr += [(f"إعداد: {k}", v) for k, v in SETTINGS_KEYS.items()]
    instr += [("وسم البيانات", "استخدم synthetic للبيانات التجريبية أو real للحقيقية، دون خلط داخل المجموعة. النسخة المنشورة تقبل synthetic فقط.")]
    b.kv(instr, "تعليمات", "تعليمات القالب")
    for key, t in REVENUE_TABLES.items():
        if key == "settings":
            df = pd.DataFrame({"key": list(SETTINGS_KEYS), "value": ["2026", "100000000", "2026-09-30", "cash", "synthetic", "وصف المصدر"]})
        else:
            df = pd.DataFrame(columns=t.col_names)
        b.table(df, key)
    return b.bytes()


def perf_template_excel(perf=None) -> bytes:
    b = _Book()
    instr = [
        ("الغرض", "قالب استيراد نتائج الأداء الشهرية: صف لكل (قسم، شهر، مؤشر)."),
        ("القيم", "المستهدف والمحقق بين 0 و100. المستهدف يجب أن يكون أكبر من صفر. اترك المحقق فارغًا إن لم يُدخل — الفراغ لا يُعامل كصفر."),
        ("التكرار", "لا يُسمح بتكرار (القسم، الشهر، المؤشر). رفع شهر موجود يستبدل بيانات ذلك القسم لذلك الشهر فقط."),
        ("الأوراق الاختيارية", "general_departments و departments لتحديث الأسماء أو إضافة أقسام بمعرفات ثابتة."),
    ]
    b.kv(instr, "تعليمات", "تعليمات القالب")
    if perf is not None:
        sample = []
        for d in perf.depts[perf.depts["active"].astype(bool)].itertuples():
            for k in perf.kpis.itertuples():
                sample.append({"dept_id": d.dept_id, "month": "2026-10", "kpi_id": k.kpi_id, "target": "", "actual": "", "data_label": perf.label or "synthetic"})
        b.table(pd.DataFrame(sample, columns=PERF_TABLES["performance_records"].col_names), "performance_records")
        b.table(perf.depts, "departments")
        b.table(perf.gds, "general_departments")
        b.table(perf.kpis, "kpi_definitions")
    else:
        b.table(pd.DataFrame(columns=PERF_TABLES["performance_records"].col_names), "performance_records")
    return b.bytes()


def csv_bytes(df: pd.DataFrame) -> bytes:
    return _prep(df).to_csv(index=False).encode("utf-8-sig")
