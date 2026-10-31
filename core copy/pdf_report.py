"""تقارير PDF عربية (اتجاه من اليمين لليسار) باستخدام ReportLab + arabic_reshaper + python-bidi.

الالتفاف يتم على النص المنطقي (قبل إعادة الترتيب البصري) ثم يُعاد ترتيب كل سطر على حدة،
حتى تبقى بداية الجملة في السطر الأول على اليمين."""
from __future__ import annotations

import io
import re
from datetime import datetime
from functools import lru_cache
from xml.sax.saxutils import escape

import arabic_reshaper
from bidi.algorithm import get_display  # التنفيذ الذي يعكس الأقواس بشكل صحيح
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .config import APP_NAME_AR, APP_VERSION, FONTS_DIR, LOGO_DIR, ORG_NAME_AR, PROTOTYPE_NOTICE, SCENARIOS_DEFAULT, STATUS_META, SYNTHETIC_NOTICE
from .formatting import fmt_m, fmt_pct, fmt_points, fmt_sar, month_label
from .opportunities import EASE_LABELS, RISK_LABELS

GREEN = colors.HexColor("#0E5A43")
GREEN_50 = colors.HexColor("#EAF3EF")
GOLD = colors.HexColor("#A9853A")
INK = colors.HexColor("#17211D")
MUTED = colors.HexColor("#5A6660")
LINE = colors.HexColor("#DCE3DF")
PAGE_W, PAGE_H = A4
MARGIN = 16 * mm
CONTENT_W = PAGE_W - 2 * MARGIN
RESHAPER = arabic_reshaper.ArabicReshaper(configuration={"delete_harakat": False, "support_ligatures": True})


@lru_cache(maxsize=1)
def register_fonts():
    pdfmetrics.registerFont(TTFont("Plex", str(FONTS_DIR / "IBMPlexSansArabic-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Plex-Bold", str(FONTS_DIR / "IBMPlexSansArabic-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Plex-Medium", str(FONTS_DIR / "IBMPlexSansArabic-Medium.ttf")))
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily("Plex", normal="Plex", bold="Plex-Bold", italic="Plex", boldItalic="Plex-Bold")
    return True


def shape(text: str) -> str:
    return RESHAPER.reshape(str(text))


ARABIC_RE = re.compile(r"[\u0600-\u06FF\uFB50-\uFEFF]")


def visual(text: str) -> str:
    """نص منطقي -> نص بصري جاهز للرسم من اليسار لليمين.
    الأسطر الخالية من الحروف العربية (معادلات وأرقام) تبقى باتجاه من اليسار لليمين."""
    if not ARABIC_RE.search(str(text)):
        return str(text)
    return get_display(shape(text), base_dir="R")


def wrap_logical(text: str, font: str, size: float, width: float) -> list[str]:
    lines = []
    for para in str(text).split("\n"):
        words = para.split(" ")
        cur = ""
        for w in words:
            cand = w if not cur else cur + " " + w
            if pdfmetrics.stringWidth(shape(cand), font, size) <= width or not cur:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def styles():
    register_fonts()
    base = dict(fontName="Plex", fontSize=9, leading=13.5, alignment=TA_RIGHT, textColor=INK)
    return {
        "body": ParagraphStyle("body", **base),
        "small": ParagraphStyle("small", **{**base, "fontSize": 8, "leading": 11.5, "textColor": MUTED}),
        "h1": ParagraphStyle("h1", **{**base, "fontName": "Plex-Bold", "fontSize": 16, "leading": 22, "textColor": GREEN}),
        "h2": ParagraphStyle("h2", **{**base, "fontName": "Plex-Bold", "fontSize": 12, "leading": 17, "textColor": GREEN}),
        "h3": ParagraphStyle("h3", **{**base, "fontName": "Plex-Bold", "fontSize": 10, "leading": 14}),
        "cell": ParagraphStyle("cell", **{**base, "fontSize": 8, "leading": 11}),
        "cellb": ParagraphStyle("cellb", **{**base, "fontName": "Plex-Bold", "fontSize": 8, "leading": 11, "textColor": colors.white}),
        "cellc": ParagraphStyle("cellc", **{**base, "fontSize": 8, "leading": 11, "alignment": TA_CENTER}),
        "note": ParagraphStyle("note", **{**base, "fontSize": 8.5, "leading": 12.5, "textColor": colors.HexColor("#6B4E10")}),
    }


def P(text, style: ParagraphStyle, width: float | None = None) -> Paragraph:
    width = width or CONTENT_W
    # هامش أمان يغطي حشوات الإطار/الخلية (6 نقاط لكل جانب) حتى لا يعيد ReportLab الالتفاف
    lines = wrap_logical(text, style.fontName, style.fontSize, width - 16)
    vis = "<br/>".join(escape(visual(l)) for l in lines)
    return Paragraph(vis, style)


def rtl_table(header: list, rows: list, widths: list, st: dict, highlight_rows: set | None = None, center_cols: set | None = None, row_bg: dict | None = None) -> Table:
    """جدول RTL: العمود الأول منطقيًا يظهر على اليمين."""
    center_cols = center_cols or set()
    data = [[P(h, st["cellb"], w) for h, w in zip(header, widths)]]
    for r in rows:
        data.append([P("" if v is None else v, st["cellc"] if j in center_cols else st["cell"], w) for j, (v, w) in enumerate(zip(r, widths))])
    data = [list(reversed(r)) for r in data]
    t = Table(data, colWidths=list(reversed(widths)), repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in (highlight_rows or set()):
        style.append(("BACKGROUND", (0, i + 1), (-1, i + 1), GREEN_50))
    for i, c in (row_bg or {}).items():
        style.append(("BACKGROUND", (0, i + 1), (-1, i + 1), colors.HexColor(c)))
    t.setStyle(TableStyle(style))
    return t


def _logo_flowable(height=16 * mm):
    for name in ("hail_logo.png", "hail_logo.jpg", "logo.png"):
        p = LOGO_DIR / name
        if p.exists():
            img = Image(str(p))
            ratio = img.imageWidth / img.imageHeight
            img.drawHeight = height
            img.drawWidth = height * ratio
            img.hAlign = "RIGHT"
            return img
    return None


def _header(st, title: str, subtitle: str):
    out = []
    logo = _logo_flowable()
    if logo is not None:
        out.append(logo)
    else:
        out.append(P(ORG_NAME_AR, st["h3"]))
    out += [Spacer(1, 2 * mm), P(title, st["h1"]), P(subtitle, st["small"]), Spacer(1, 5 * mm)]
    return out


def _closing(st):
    """حالة النظام والبيانات في آخر التقرير (وفي تذييل كل صفحة) بدل أعلى الصفحة الأولى."""
    box = Table([[P(f"{PROTOTYPE_NOTICE}. {SYNTHETIC_NOTICE}. لا يوجد نموذج تعلم آلة مدرب؛ النتائج مبنية على قواعد تحليلية وافتراضات موضحة في التقرير.", st["small"])]], colWidths=[CONTENT_W])
    box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINE), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return [Spacer(1, 6 * mm), box]


def _footer(canvas, doc):
    register_fonts()
    canvas.saveState()
    canvas.setFont("Plex", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_W - MARGIN, 9 * mm, visual(f"{APP_NAME_AR} — {PROTOTYPE_NOTICE} — الإصدار {APP_VERSION}"))
    canvas.drawRightString(PAGE_W - MARGIN, 5.5 * mm, visual(SYNTHETIC_NOTICE))
    canvas.drawString(MARGIN, 9 * mm, f"{doc.page}")
    canvas.setStrokeColor(LINE)
    canvas.line(MARGIN, 12.5 * mm, PAGE_W - MARGIN, 12.5 * mm)
    canvas.restoreState()


def _bridge_chart(items: list, width=CONTENT_W, height=62 * mm) -> Drawing:
    """أعمدة أفقية بسيطة: [(التسمية، القيمة، اللون)] — التسميات على اليمين والأعمدة تمتد لليسار."""
    register_fonts()
    d = Drawing(width, height)
    n = len(items)
    label_w = 62 * mm
    val_w = 30 * mm
    bar_area = width - label_w - val_w
    mx = max(v for _, v, _ in items) or 1
    row_h = height / n
    for i, (lab, v, col) in enumerate(items):
        y = height - (i + 1) * row_h + row_h * 0.25
        bh = row_h * 0.5
        bw = bar_area * (v / mx)
        x_right = width - label_w - 3
        d.add(Rect(x_right - bw, y, bw, bh, fillColor=colors.HexColor(col), strokeColor=None))
        d.add(String(width, y + bh * 0.3, visual(lab), fontName="Plex", fontSize=8, fillColor=INK, textAnchor="end"))
        d.add(String(x_right - bw - 4, y + bh * 0.3, visual(fmt_m(v)), fontName="Plex", fontSize=8, fillColor=MUTED, textAnchor="end"))
    d.add(Line(width - label_w - 3, 0, width - label_w - 3, height, strokeColor=LINE, strokeWidth=0.6))
    return d


def revenue_pdf(data, kpis: dict, opps, excluded, scenario_key: str, multipliers: dict, result: dict, weights: dict) -> bytes:
    st = styles()
    s = data.settings
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=MARGIN, leftMargin=MARGIN, topMargin=14 * mm, bottomMargin=18 * mm,
                            title="Revenue Opportunities Report", author="Prototype")
    sc_label = SCENARIOS_DEFAULT[scenario_key]["label"]
    story = _header(st, "تقرير فرص تنمية الإيرادات", f"{ORG_NAME_AR} — {APP_NAME_AR}")
    meta = [
        ("تاريخ البيانات (اللقطة)", s.snapshot_date.isoformat()),
        ("مصدر البيانات", s.source_note),
        ("وسم البيانات", "تجريبية (synthetic)" if s.data_label == "synthetic" else "حقيقية (real)"),
        ("الأساس المالي", s.basis_label),
        ("السيناريو المختار", f"{sc_label} — معامل حساسية {multipliers[scenario_key]:.0%} (افتراض وليس فاصل ثقة)"),
        ("تاريخ إنشاء التقرير", datetime.now().strftime("%Y-%m-%d %H:%M")),
    ]
    story.append(rtl_table(["البند", "القيمة"], meta, [55 * mm, CONTENT_W - 55 * mm], st))
    story.append(Spacer(1, 4 * mm))
    story.append(P("الفجوة والإيرادات", st["h2"]))
    att = "غير قابلة للحساب (المستهدف صفر)" if kpis["attainment_pct"] is None else fmt_pct(kpis["attainment_pct"])
    krows = [
        ("المستهدف السنوي", fmt_sar(kpis["target"])),
        ("المحقق حتى تاريخ اللقطة", fmt_sar(kpis["realized"])),
        ("الفجوة حتى تاريخ اللقطة", fmt_sar(kpis["gap_to_date"])),
        ("نسبة تحقيق المستهدف", att),
        ("الإيراد الأساسي المتوقع لبقية السنة (دون فرص جديدة)", fmt_sar(kpis["baseline_remaining"])),
        ("الفجوة المتوقعة بنهاية السنة قبل الفرص", fmt_sar(kpis["projected_gap"])),
        ("إيراد متكرر خلال السنة من الفرص المختارة", fmt_sar(result["recurring_in_year"])),
        ("تحصيل لمرة واحدة خلال السنة", fmt_sar(result["one_time_in_year"]) + ("" if s.financial_basis == "cash" else " (أثر نقدي فقط — لا يُحتسب على أساس الاستحقاق)")),
        ("الفجوة المتبقية بعد الفرص المختارة", fmt_sar(result["remaining_gap"])),
        ("الفائض المتوقع", fmt_sar(result["surplus"])),
    ]
    story.append(rtl_table(["المؤشر", "القيمة"], krows, [90 * mm, CONTENT_W - 90 * mm], st, highlight_rows={8}))
    story.append(Spacer(1, 3 * mm))
    items = [
        ("المستهدف السنوي", kpis["target"], "#9AA5A0"),
        ("المحقق حتى تاريخ اللقطة", kpis["realized"], "#0E5A43"),
        ("المتوقع بنهاية السنة قبل الفرص", kpis["projected_year_end"], "#3E8E6E"),
        ("المتوقع بعد الفرص المختارة", result["projected_with_opps"], "#A9853A"),
    ]
    story.append(KeepTogether([P("مقارنة المستهدف بالمحقق والمتوقع", st["h3"]), _bridge_chart(items, height=36 * mm)]))
    story.append(P("التقديرات تحليلية مبنية على بيانات وافتراضات موضحة أدناه وليست حقائق مالية مؤكدة. الإيراد المعروض قبل خصم تكاليف التنفيذ والتشغيل (إيراد وليس ربحًا). الاقتراحات ليست موافقة تنظيمية أو إذنًا بالتنفيذ.", st["note"]))

    sel = result["selection"].kept
    dropped = dict(result["selection"].dropped)
    det = result["detail"].set_index("opp_id") if not result["detail"].empty else None
    story.append(Spacer(1, 4 * mm))
    story.append(P(f"الفرص المختارة في السيناريو ({len(sel)})", st["h2"]))
    if sel:
        rows = []
        for oid in sel:
            o = opps.loc[opps["opp_id"] == oid].iloc[0]
            rows.append((str(o["rank"]), oid, o["title"], o["nature_label"], fmt_sar(det.at[oid, "in_year"]), fmt_sar(o["annual_potential"]) if o["nature"] == "recurring" else "—", EASE_LABELS[o["ease"]], RISK_LABELS[o["risk"]]))
        story.append(rtl_table(["#", "المعرف", "الفرصة", "الطبيعة", f"خلال السنة ({sc_label})", "سنوي محتمل", "السهولة", "المخاطر"],
                               rows, [8 * mm, 26 * mm, 48 * mm, 20 * mm, 26 * mm, 22 * mm, 14 * mm, 14 * mm], st, highlight_rows=set(range(len(rows))), center_cols={0, 6, 7}))
    else:
        story.append(P("لم تُختر أي فرصة في هذا السيناريو.", st["body"]))
    if dropped:
        story.append(Spacer(1, 2 * mm))
        story.append(P("فرص اختيرت ثم استُبعدت تلقائيًا لمنع التعارض أو التكرار:", st["h3"]))
        for k, v in dropped.items():
            story.append(P(f"• {k}: {v}", st["small"]))
    others = opps[~opps["opp_id"].isin(sel)]
    story.append(Spacer(1, 4 * mm))
    story.append(P(f"فرص أخرى غير مختارة ({len(others)})", st["h2"]))
    if len(others):
        rows = [(str(o.rank), o.opp_id, o.title, o.nature_label, fmt_sar(o.in_year), fmt_sar(o.annual_potential) if o.nature == "recurring" else fmt_sar(o.one_time_total), f"{o.priority_score:.1f}") for o in others.itertuples()]
        story.append(rtl_table(["#", "المعرف", "الفرصة", "الطبيعة", "خلال السنة (أساسي)", "سنوي/إجمالي الحملة", "الأولوية"],
                               rows, [8 * mm, 27 * mm, 60 * mm, 20 * mm, 26 * mm, 25 * mm, 12 * mm], st, center_cols={0, 6}))

    story.append(PageBreak())
    story.append(P("تفاصيل الفرص المختارة: الأدلة والحساب والافتراضات", st["h2"]))
    for oid in sel:
        o = opps.loc[opps["opp_id"] == oid].iloc[0]
        block = [P(f"{oid} — {o['title']}", st["h3"]),
                 P(f"النوع: {o['type_label']} | المرجع: {o['ref_type']} {o['ref_ids'][:120]} | بدء الأثر: {o['effective_date'].isoformat()} | المهلة: {o['lead_days']} يومًا | السهولة: {EASE_LABELS[o['ease']]} | المخاطر: {RISK_LABELS[o['risk']]}", st["small"]),
                 P("سبب الاقتراح: " + o["reason"], st["body"])]
        ev = [(a, b) for a, b in o["evidence"]]
        block.append(rtl_table(["الدليل", "القيمة من البيانات"], ev, [55 * mm, CONTENT_W - 55 * mm], st))
        block.append(P("طريقة الحساب:", st["h3"]))
        block.append(P(o["method"], st["body"]))
        block.append(P("الافتراضات:", st["h3"]))
        for a in o["assumptions"]:
            block.append(P("• " + a, st["body"]))
        block.append(P("المراجعات والموافقات المطلوبة قبل أي تنفيذ:", st["h3"]))
        for a in o["approvals"]:
            block.append(P("• " + a, st["body"]))
        block.append(Spacer(1, 5 * mm))
        story.append(KeepTogether(block[:4]))
        story.extend(block[4:])

    story.append(P("المنهجية", st["h2"]))
    for line in [
        f"ترتيب الأولوية: الدرجة = ({weights['contribution']}% × مساهمة السنة المعيارية + {weights['ease']}% × السهولة المعيارية + {weights['risk']}% × عكس المخاطر). الدرجة نسبية للمقارنة بين الفرص وليست احتمال نجاح.",
        "مساهمة السنة: لا يُحتسب أي أثر قبل انتهاء مهلة التنفيذ أو تاريخ التجديد، ويُحتسب الإيراد المتكرر بنسبة الأيام المتبقية من السنة فقط.",
        "منع الازدواج: يُطرح الإيراد الأساسي المدرج والتحصيل المتوقع أصلًا، ويُستبعد المسدد سابقًا، ولا تُجمع فرص متعارضة على الأصل أو المدين نفسه.",
        "السيناريوهات: " + "، ".join(f"{SCENARIOS_DEFAULT[k]['label']} {v:.0%}" for k, v in multipliers.items()) + " — معاملات حساسية افتراضية مع سقوف منطقية (إشغال كامل، سقف تعاقدي/مرجعي، الرصيد المستحق).",
        "الذكاء الاصطناعي: لا يوجد نموذج تعلم آلة مدرب في هذا الإصدار لعدم توفر بيانات تاريخية حقيقية؛ المحرك قواعد تحليلية قابلة للتفسير.",
    ]:
        story.append(P("• " + line, st["body"]))
    if excluded is not None and len(excluded):
        story.append(Spacer(1, 3 * mm))
        story.append(P("ما الذي استُبعد ولماذا", st["h2"]))
        story.append(rtl_table(["المرجع", "النوع", "السبب"], [tuple(r) for r in excluded.itertuples(index=False)], [26 * mm, 18 * mm, CONTENT_W - 44 * mm], st))
    story += _closing(st)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def perf_pdf(perf, gd_id: str, month: str, settings, summary) -> bytes:
    from .performance import gd_kpis
    st = styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=MARGIN, leftMargin=MARGIN, topMargin=14 * mm, bottomMargin=18 * mm, title="Department Performance Summary")
    gd_name = perf.gds.set_index("gd_id").at[gd_id, "gd_name"]
    story = _header(st, f"ملخص أداء الأقسام — {month_label(month)}", f"{gd_name} — {APP_NAME_AR}")
    k = gd_kpis(summary)
    meta = [
        ("الإدارة العامة", f"{gd_name} ({gd_id})"),
        ("الشهر", month_label(month)),
        ("مصدر البيانات", "بيانات تجريبية (synthetic)" if perf.label == "synthetic" else "بيانات مدخلة/مستوردة (real)"),
        ("تاريخ التصدير", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("عدد الأقسام / المكتملة", f"{k['n_depts']} / {k['n_complete']}"),
        ("متوسط الأداء (للمكتملة)", "—" if k["avg_score"] is None else fmt_pct(k["avg_score"])),
        ("تحتاج تدخلًا", str(k["n_intervene"])),
        ("الأوزان", "، ".join(f"{r.kpi_name} {settings.weights.get(r.kpi_id, 0):g}%" for r in perf.kpis.itertuples())),
        ("حدود التصنيف", f"جيد ≥ {settings.green:g}% | متوسط {settings.yellow:g}% إلى أقل من {settings.green:g}% | يحتاج تدخل < {settings.yellow:g}% | بيانات ناقصة عند نقص أي مدخل"),
    ]
    story.append(rtl_table(["البند", "القيمة"], meta, [50 * mm, CONTENT_W - 50 * mm], st))
    story.append(Spacer(1, 4 * mm))
    story.append(P("نتائج الأقسام", st["h2"]))
    rows, bgs = [], {}
    for i, r in enumerate(summary.itertuples()):
        rows.append((r.dept_name, "—" if r.score is None or r.score != r.score else fmt_pct(r.score), r.status_label, fmt_points(r.delta) if r.delta is not None and r.delta == r.delta else r.compare_note, r.reason))
        bgs[i] = STATUS_META[r.status]["bg"]
    story.append(rtl_table(["القسم", "الدرجة", "الحالة", "التغير عن الشهر السابق", "سبب التصنيف"], rows, [38 * mm, 16 * mm, 20 * mm, 32 * mm, CONTENT_W - 106 * mm], st, center_cols={1, 2}, row_bg=bgs))
    story.append(Spacer(1, 4 * mm))
    story.append(P("المؤشرات والمستهدفات والمحقق", st["h2"]))
    rows = []
    for r in summary.itertuples():
        for x in r.details:
            rows.append((r.dept_name, x["kpi_name"], f"{x['weight']:g}%", "—" if x["target"] is None else f"{x['target']:g}", "غير مدخل" if x["actual"] is None else f"{x['actual']:g}",
                         "—" if x["achievement"] is None else fmt_pct(x["achievement"]), "نعم" if x["met"] else ("—" if x["actual"] is None else "لا")))
    story.append(rtl_table(["القسم", "المؤشر", "الوزن", "المستهدف", "المحقق", "التحقيق (بسقف 100%)", "حقق المستهدف"], rows,
                           [40 * mm, 30 * mm, 14 * mm, 18 * mm, 18 * mm, 26 * mm, CONTENT_W - 146 * mm], st, center_cols={2, 3, 4, 5, 6}))
    story.append(Spacer(1, 3 * mm))
    story.append(P("طريقة الحساب: تحقيق المؤشر = المحقق ÷ المستهدف × 100 بسقف 100% حتى لا يعوض تجاوز مؤشر ضعف مؤشر آخر؛ درجة القسم = المتوسط المرجح بالأوزان؛ القيمة غير المدخلة لا تُعامل كصفر. المقارنة مع الشهر التقويمي السابق فقط عند اكتمال بياناته.", st["body"]))
    story.append(P("هذه إعدادات تجريبية تحتاج اعتماد الإدارة وليست معايير رسمية للأمانة. اللوحة لمتابعة أداء الأقسام وليست نظامًا لاتخاذ قرارات أو جزاءات آلية بحق الموظفين.", st["note"]))
    story += _closing(st)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
