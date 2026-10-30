"""يولّد القوالب (CSV/Excel) وأمثلة التقارير (PDF/Excel) من البيانات التجريبية.

python scripts/make_samples.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import ENGINE_DEFAULTS, PRIORITY_WEIGHTS_DEFAULT, SCENARIOS_DEFAULT  # noqa: E402
from core.exports import csv_bytes, perf_backup_excel, perf_excel, perf_template_excel, revenue_excel, revenue_template_excel  # noqa: E402
from core.opportunities import detect_opportunities  # noqa: E402
from core.pdf_report import perf_pdf, revenue_pdf  # noqa: E402
from core.performance import default_settings, load_synthetic_perf, month_summary  # noqa: E402
from core.revenue import auto_select, compute_kpis, scenario_result  # noqa: E402
from core.revenue_data import load_synthetic_revenue  # noqa: E402
from core.schemas import PERF_TABLES, REVENUE_TABLES, SETTINGS_KEYS  # noqa: E402


def main():
    tpl = ROOT / "templates"
    smp = ROOT / "samples"
    tpl.mkdir(exist_ok=True)
    smp.mkdir(exist_ok=True)
    # القوالب
    (tpl / "revenue_template.xlsx").write_bytes(revenue_template_excel())
    perf = load_synthetic_perf()
    (tpl / "performance_template.xlsx").write_bytes(perf_template_excel(perf))
    # أسماء ملفات CSV يجب أن تطابق أسماء الجداول ليتعرف عليها الاستيراد
    import shutil
    shutil.rmtree(tpl / "csv", ignore_errors=True)
    (tpl / "csv" / "revenue").mkdir(parents=True)
    (tpl / "csv" / "performance").mkdir(parents=True)
    for k, t in REVENUE_TABLES.items():
        df = pd.DataFrame({"key": list(SETTINGS_KEYS), "value": ["2026", "100000000", "2026-09-30", "cash", "synthetic", "وصف المصدر"]}) if k == "settings" else pd.DataFrame(columns=t.col_names)
        (tpl / "csv" / "revenue" / f"{k}.csv").write_bytes(csv_bytes(df))
    for k, t in PERF_TABLES.items():
        (tpl / "csv" / "performance" / f"{k}.csv").write_bytes(csv_bytes(pd.DataFrame(columns=t.col_names)))

    # أمثلة الإيرادات: السيناريو المتوسط مع الاختيار التلقائي
    rev = load_synthetic_revenue()
    k = compute_kpis(rev)
    opps, ex = detect_opportunities(rev)
    mult = {kk: v["multiplier"] for kk, v in SCENARIOS_DEFAULT.items()}
    sel = auto_select(opps, k, 1.0, rev.settings.financial_basis)
    res = scenario_result(opps, sel, 1.0, k, rev.settings.financial_basis)
    allr = {kk: scenario_result(opps, sel, m, k, rev.settings.financial_basis) for kk, m in mult.items()}
    (smp / "sample_revenue_report_base.pdf").write_bytes(revenue_pdf(rev, k, opps, ex, "base", mult, res, PRIORITY_WEIGHTS_DEFAULT))
    (smp / "sample_revenue_results_base.xlsx").write_bytes(revenue_excel(rev, k, opps, ex, "base", mult, res, allr, PRIORITY_WEIGHTS_DEFAULT, ENGINE_DEFAULTS))

    # أمثلة الأداء
    s = default_settings(perf)
    sm = month_summary(perf, "GD-A", "2026-09", s)
    (smp / "sample_performance_GD-A_2026-09.xlsx").write_bytes(perf_excel(perf, "GD-A", "2026-09", s, sm))
    (smp / "sample_performance_GD-A_2026-09.pdf").write_bytes(perf_pdf(perf, "GD-A", "2026-09", s, sm))
    (smp / "sample_performance_backup.xlsx").write_bytes(perf_backup_excel(perf))
    print("القوالب:", sorted(p.name for p in tpl.rglob("*") if p.is_file()))
    print("الأمثلة:", sorted(p.name for p in smp.iterdir()))
    print(f"فرص: {len(opps)} — مختارة: {len(sel)} — مساهمة: {res['contribution']:,.0f} — فجوة متبقية: {res['remaining_gap']:,.0f}")


if __name__ == "__main__":
    main()
