"""تصدير PDF وExcel للإيرادات والأداء."""
from __future__ import annotations

import io

import openpyxl
from pypdf import PdfReader

from core.config import ENGINE_DEFAULTS, PRIORITY_WEIGHTS_DEFAULT, SCENARIOS_DEFAULT
from core.exports import perf_excel, revenue_excel, revenue_template_excel, perf_template_excel
from core.opportunities import detect_opportunities
from core.pdf_report import perf_pdf, revenue_pdf, visual
from core.performance import default_settings, month_summary
from core.revenue import auto_select, compute_kpis, scenario_result

MULT = {k: v["multiplier"] for k, v in SCENARIOS_DEFAULT.items()}


def _rev(rev):
    k = compute_kpis(rev)
    opps, ex = detect_opportunities(rev)
    sel = auto_select(opps, k, 1.0, "cash")[:5]
    res = scenario_result(opps, sel, 1.0, k, "cash")
    return k, opps, ex, sel, res


def test_revenue_pdf_valid(rev):
    k, opps, ex, sel, res = _rev(rev)
    pdf = revenue_pdf(rev, k, opps, ex, "base", MULT, res, PRIORITY_WEIGHTS_DEFAULT)
    assert pdf[:4] == b"%PDF"
    r = PdfReader(io.BytesIO(pdf))
    assert len(r.pages) >= 3
    fonts = " ".join(str(f.get_object().get("/BaseFont")) for f in r.pages[0]["/Resources"]["/Font"].values())
    assert "IBMPlexSansArabic" in fonts  # الخط العربي مضمّن في الملف


def test_arabic_visual_order_and_mirroring():
    v = visual("تاريخ (اللقطة)")
    assert v.startswith("(") and v.endswith("ﺦﻳﺭﺎﺗ")  # الأقواس معكوسة صحيحًا والنص من اليمين
    assert visual("1,420,000 × 0.5 = 710,000") == "1,420,000 × 0.5 = 710,000"  # المعادلات تبقى LTR


def test_revenue_excel_contents(rev):
    k, opps, ex, sel, res = _rev(rev)
    allr = {kk: scenario_result(opps, sel, m, k, "cash") for kk, m in MULT.items()}
    x = revenue_excel(rev, k, opps, ex, "base", MULT, res, allr, PRIORITY_WEIGHTS_DEFAULT, ENGINE_DEFAULTS)
    wb = openpyxl.load_workbook(io.BytesIO(x))
    for name in ("الملخص", "الفرص", "المستبعد", "السيناريوهات", "المنهجية والإعدادات"):
        assert name in wb.sheetnames
    assert any(n.startswith("مدخلات_") for n in wb.sheetnames)
    ws = wb["الفرص"]
    assert ws.sheet_view.rightToLeft
    states = [c.value for c in ws["C"][4:]]
    assert states.count("مختارة") == len(sel)
    summ = {r[0].value: r[1].value for r in wb["الملخص"].iter_rows(min_row=5)}
    assert summ["المستهدف السنوي (ريال)"] == 100_000_000
    assert abs(summ["الفجوة المتبقية بعد الفرص (ريال)"] - round(res["remaining_gap"], 2)) < 0.01


def test_perf_exports(perf):
    s = default_settings(perf)
    sm = month_summary(perf, "GD-A", "2026-09", s)
    x = perf_excel(perf, "GD-A", "2026-09", s, sm)
    wb = openpyxl.load_workbook(io.BytesIO(x))
    summ = {r[0].value: r[1].value for r in wb["الملخص"].iter_rows(min_row=5)}
    assert "50%" in summ["الأوزان"] and "90%" in summ["حدود التصنيف"]
    assert wb["نتائج الأقسام"].max_row == 4 + 6
    rows = list(wb["المؤشرات والمدخلات"].iter_rows(min_row=5, values_only=True))
    assert len(rows) == 18
    pdf = perf_pdf(perf, "GD-A", "2026-09", s, sm)
    assert pdf[:4] == b"%PDF" and len(PdfReader(io.BytesIO(pdf)).pages) >= 1


def test_templates_open():
    for b in (revenue_template_excel(), perf_template_excel()):
        wb = openpyxl.load_workbook(io.BytesIO(b))
        assert "تعليمات" in wb.sheetnames
