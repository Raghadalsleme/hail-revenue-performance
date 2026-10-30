"""يولّد البيانات التجريبية (Synthetic) للمنصة بشكل حتمي (seed ثابت).

Synthetic Data — بيانات تجريبية لا تمثل أرقام أمانة منطقة حائل.
الأسماء والأرقام والأحياء المستخدمة لأغراض العرض فقط، والأسماء الإدارية لا تمثل الهيكل التنظيمي للأمانة.

التشغيل: python scripts/generate_synthetic_data.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "synthetic"
L = "synthetic"
SNAP = date(2026, 9, 30)
rng = np.random.default_rng(20261030)


def settings():
    return pd.DataFrame(
        [
            ("fiscal_year", "2026"),
            ("annual_target_sar", "100000000"),
            ("snapshot_date", SNAP.isoformat()),
            ("financial_basis", "cash"),
            ("data_label", L),
            ("source_note", "بيانات تجريبية مولدة آليًا (Synthetic) لأغراض العرض — لا تمثل أرقام أمانة منطقة حائل"),
        ],
        columns=["key", "value"],
    )


def sources():
    rows = [
        ("SRC01", "رسوم رخص البناء", "رسوم", 9_500_000, 7_600_000, 1_300_000),
        ("SRC02", "رسوم الرخص التجارية البلدية", "رسوم", 13_000_000, 11_200_000, 1_200_000),
        ("SRC03", "إيجارات العقود الاستثمارية", "استثمار", 38_000_000, 30_400_000, 4_100_000),
        ("SRC04", "رسوم اللوحات الإعلانية", "استثمار", 7_000_000, 5_300_000, 900_000),
        ("SRC05", "الغرامات والجزاءات البلدية", "غرامات", 8_000_000, 6_100_000, 1_000_000),
        ("SRC06", "رسوم الإشغالات المؤقتة", "رسوم", 5_000_000, 3_800_000, 600_000),
        ("SRC07", "إيرادات الأسواق والمسالخ", "خدمات", 6_500_000, 5_000_000, 1_100_000),
        ("SRC08", "رسوم الشهادات والتقارير الفنية", "رسوم", 3_000_000, 2_400_000, 450_000),
        ("SRC09", "تحصيل متأخرات سنوات سابقة", "تحصيل", 6_000_000, 4_200_000, 600_000),
        ("SRC10", "إيرادات أخرى", "أخرى", 4_000_000, 4_000_000, 250_000),
    ]
    df = pd.DataFrame(rows, columns=["source_id", "source_name", "category", "annual_target_sar", "realized_to_date_sar", "expected_remaining_sar"])
    df["data_label"] = L
    assert df["annual_target_sar"].sum() == 100_000_000
    assert df["realized_to_date_sar"].sum() == 80_000_000
    return df


def benchmarks():
    rows = []
    spec = {
        "أرض تجارية": ("م²", 0.90, {"A": (110, 135), "B": (80, 100), "C": (55, 70)}),
        "أرض خدمية": ("م²", 0.90, {"A": (70, 90), "B": (50, 65), "C": (35, 45)}),
        "أرض ترفيهية (موسمي)": ("م²", 0.70, {"A": (40, 55), "B": (28, 38)}),  # لا يوجد مرجع للفئة C عمدًا
        "محل تجاري": ("م²", 0.90, {"A": (950, 1150), "B": (700, 850), "C": (480, 600)}),
        "مكاتب": ("م²", 0.85, {"A": (520, 620), "B": (420, 500), "C": (300, 360)}),
        "كشك": ("م²", 0.90, {"A": (3200, 3800), "B": (2600, 3100), "C": (1800, 2200)}),
        "لوحة إعلانية": ("لوحة", 0.85, {"A": (180_000, 220_000), "B": (120_000, 150_000), "C": (70_000, 90_000)}),
    }
    i = 1
    for cat, (unit, occ, tiers) in spec.items():
        for tier, (ref, up) in tiers.items():
            rows.append((f"BM-{i:02d}", cat, tier, unit, ref, up, occ, "2026-06-30", "مرجع سوقي تجريبي (Synthetic) — يحتاج تقييمًا معتمدًا"))
            i += 1
    df = pd.DataFrame(rows, columns=["benchmark_id", "category", "location_tier", "unit", "ref_annual_rate_sar", "upper_annual_rate_sar", "expected_occupancy", "as_of_date", "source_note"])
    df["data_label"] = L
    return df


ASSET_COLS = ["asset_id", "asset_name", "asset_type", "district", "location_tier", "zoning", "area_sqm", "frontage_m", "on_main_road",
              "utilities_available", "status", "current_occupancy", "current_annual_revenue_sar", "restricted", "restriction_reason"]


def candidate_assets():
    """أصول غير مستغلة/مستغلة جزئيًا أو مقيدة — مصممة لتغطية كل مسارات المحرك."""
    return [
        ("AST-001", "أرض تجارية على طريق الملك عبدالعزيز", "أرض فضاء", "النقرة", "A", "تجاري", 6200, 120, True, True, "غير مستغل", 0, 0, False, ""),
        ("AST-002", "أرض استثمارية متعددة الاستخدام", "أرض فضاء", "المنتزه", "B", "استثماري متعدد", 9800, 60, True, False, "غير مستغل", 0, 0, False, ""),
        ("AST-003", "أرض خدمية مخصصة للاستثمار", "أرض فضاء", "الخزامى", "B", "خدمي", 7500, 50, False, True, "غير مستغل", 0, 0, False, ""),
        ("AST-004", "ساحة فعاليات مفتوحة", "أرض فضاء", "السمراء", "B", "ترفيهي", 15000, 80, True, True, "غير مستغل", 0, 0, False, ""),
        ("AST-005", "مجمع محلات بلدي", "محل تجاري", "الوسيطاء", "A", "تجاري", 1800, 90, True, True, "مستغل جزئيًا", 0.45, 664_200, False, ""),
        ("AST-006", "مبنى مكاتب بلدي", "مبنى مكاتب", "صبابة", "B", "تجاري", 2400, 40, True, True, "مستغل جزئيًا", 0.30, 273_600, False, ""),
        ("AST-007", "أكشاك الممشى", "كشك", "لبدة", "B", "تجاري", 24, 6, False, True, "غير مستغل", 0, 0, False, ""),
        ("AST-008", "أكشاك حديقة الحي", "كشك", "المنتزه", "A", "تجاري", 30, 8, False, True, "غير مستغل", 0, 0, False, ""),
        ("AST-009", "أرض بتصنيف سكني", "أرض فضاء", "الجامعيين", "C", "سكني", 3000, 30, False, True, "غير مستغل", 0, 0, False, ""),
        ("AST-010", "أرض تجارية محل نزاع", "أرض فضاء", "البادية", "A", "تجاري", 5000, 70, True, True, "غير مستغل", 0, 0, True, "نزاع قانوني قائم على الملكية"),
        ("AST-011", "أرض مخصصة لمرفق عام", "أرض فضاء", "مشار", "B", "خدمي", 6000, 45, False, True, "غير مستغل", 0, 0, True, "مخصصة لمرفق تعليمي حكومي (تخصيص قائم)"),
        ("AST-012", "أرض تجارية داخلية", "أرض فضاء", "الزبارة", "C", "تجاري", 4200, 35, False, True, "غير مستغل", 0, 0, False, ""),
        ("AST-013", "أرض ضمن حرم طريق مخطط", "أرض فضاء", "النصية", "B", "تجاري", 2800, 60, True, True, "غير مستغل", 0, 0, True, "تقع ضمن حرم طريق مخطط"),
        ("AST-014", "محلات السوق الشعبي", "محل تجاري", "برزان", "A", "تجاري", 900, 60, True, True, "مستغل جزئيًا", 0.60, 486_000, False, ""),
        ("AST-015", "أرض ترفيهية طرفية", "أرض فضاء", "الأجفر", "C", "ترفيهي", 12000, 100, True, False, "غير مستغل", 0, 0, False, ""),
        ("AST-016", "محلات مستغلة بالكامل", "محل تجاري", "العزيزية", "B", "تجاري", 600, 40, True, True, "مستغل", 1.0, 410_000, False, ""),
    ]


CONTRACT_COLS = ["contract_id", "asset_id", "source_id", "investor_ref", "activity", "start_date", "end_date", "leased_area_sqm",
                 "annual_value_sar", "renegotiable", "max_renewal_increase_pct", "in_dispute", "status"]


def contracts_and_assets():
    """عقود قائمة على أصول مستغلة. مجموعة محددة قريبة من التجديد لاختبار القواعد، والباقي بعيد التجديد."""
    special = [
        # (contract, type, zoning, tier, district, area, value, end, reneg, cap, dispute, activity)
        ("CTR-1003", "أرض فضاء", "تجاري", "A", "النقرة", 3000, 210_000, "2026-10-31", True, 0.25, False, "معرض سيارات"),
        ("CTR-1007", "محل تجاري", "تجاري", "A", "الوسيطاء", 1200, 780_000, "2026-12-15", True, None, False, "مركز تجاري صغير"),
        ("CTR-1012", "مبنى مكاتب", "تجاري", "B", "صبابة", 1500, 450_000, "2026-11-30", True, 0.20, False, "مكاتب إدارية"),
        ("CTR-1015", "محل تجاري", "تجاري", "B", "لبدة", 800, 420_000, "2027-02-28", True, 0.15, False, "مطاعم"),
        ("CTR-1018", "أرض فضاء", "تجاري", "A", "المنتزه", 4000, 300_000, "2027-05-31", False, None, False, "محطة وقود"),
        ("CTR-1021", "محل تجاري", "تجاري", "A", "النقرة", 1000, 600_000, "2027-03-31", True, None, True, "صالة عرض"),
        ("CTR-1024", "مبنى مكاتب", "تجاري", "A", "السمراء", 1100, 560_000, "2026-12-31", True, None, False, "مكاتب خدمات"),
        ("CTR-1027", "أرض فضاء", "خدمي", "B", "الخزامى", 5000, 180_000, "2027-06-30", True, 0.30, False, "مدارس أهلية"),
        ("CTR-1030", "كشك", "تجاري", "A", "برزان", 20, 48_000, "2027-01-31", True, None, False, "مقهى صغير"),
    ]
    assets, contracts = [], []
    n_asset = 101
    for cid, typ, zon, tier, dist, area, val, end, reneg, cap, disp, act in special:
        aid = f"AST-{n_asset}"
        n_asset += 1
        assets.append((aid, f"أصل مؤجر — {act}", typ, dist, tier, zon, area * 1.0, 40, True, True, "مستغل", 1.0, val, False, ""))
        start = date.fromisoformat(end) - timedelta(days=365 * 5) + timedelta(days=1)
        src = "SRC04" if typ == "لوحة" else "SRC03"
        contracts.append((cid, aid, src, f"INVSTR-{cid[-4:]}", act, start.isoformat(), end, area, val, reneg, cap, disp, "ساري"))
    # عقود عادية بعيدة التجديد (تُبنى بقيم قريبة من المرجع)
    acts = ["مجمع تجاري", "مطاعم ومقاهٍ", "مستودعات خفيفة", "مركز خدمات سيارات", "صالة مناسبات", "مكاتب", "نشاط ترفيهي", "محطة وقود"]
    types = [("أرض فضاء", "تجاري", 100), ("محل تجاري", "تجاري", 850), ("مبنى مكاتب", "تجاري", 450), ("أرض فضاء", "خدمي", 60)]
    districts = ["النقرة", "المنتزه", "السمراء", "صبابة", "الوسيطاء", "لبدة", "البادية", "الخزامى", "المحطة", "مشار"]
    target_total = 38_000_000 - sum(x[6] for x in special)
    k = 31
    regular = []
    for i in range(31):
        typ, zon, rate = types[i % len(types)]
        tier = ["A", "B", "B", "C"][i % 4]
        mult = {"A": 1.0, "B": 0.78, "C": 0.55}[tier]
        area = float(rng.integers(8, 60) * 100) if typ == "أرض فضاء" else float(rng.integers(4, 20) * 100)
        val = round(area * rate * mult * rng.uniform(0.93, 1.05), -3)
        regular.append([typ, zon, tier, districts[i % len(districts)], area, val, acts[i % len(acts)]])
    scale = target_total / sum(r[5] for r in regular)
    for i, (typ, zon, tier, dist, area, val, act) in enumerate(regular):
        val = round(val * scale, -3)
        aid = f"AST-{n_asset}"
        n_asset += 1
        cid = f"CTR-{2001 + i}"
        end = date(2028 + (i % 4), 1 + (i % 12), 1) - timedelta(days=1)
        start = date(end.year - 5, end.month, 1) if end.month != 12 else date(end.year - 5, 12, 1)
        assets.append((aid, f"أصل مؤجر — {act}", typ, dist, tier, zon, area, 30 + 5 * (i % 6), i % 3 == 0, True, "مستغل", 1.0, val, False, ""))
        contracts.append((cid, aid, "SRC03", f"INVSTR-{2001 + i}", act, start.isoformat(), end.isoformat(), area, val, i % 5 != 0, 0.10 if i % 2 else None, False, "ساري"))
    _ = k
    return assets, contracts


RECV_COLS = ["invoice_id", "debtor_id", "debtor_type", "contract_id", "source_id", "invoice_date", "due_date", "amount_due_sar",
             "amount_paid_sar", "status", "expected_baseline_collection_sar"]


def receivables(contract_ids):
    rows = []
    n = 50001

    def add(debtor, dtype, cid, src, days_overdue, due_amt, paid=0.0, status="متأخر", baseline=0.0):
        nonlocal n
        due = SNAP - timedelta(days=int(days_overdue))
        inv_date = due - timedelta(days=30)
        rows.append((f"INV-{n}", debtor, dtype, cid, src, inv_date.isoformat(), due.isoformat(), round(due_amt, 2), round(paid, 2), status, round(baseline, 2)))
        n += 1

    big = [
        ("DBT-001", "مستثمر", "CTR-2001", [(120, 1_200_000), (150, 800_000), (240, 1_200_000)], 150_000),
        ("DBT-002", "مستثمر", "CTR-2004", [(200, 1_300_000), (300, 1_300_000)], 100_000),
        ("DBT-003", "مستثمر", "CTR-2007", [(400, 1_100_000), (520, 1_000_000)], 50_000),
        ("DBT-004", "منشأة", "", [(95, 1_000_000), (130, 900_000)], 120_000),
        ("DBT-005", "مستثمر", "CTR-2010", [(110, 600_000), (260, 500_000), (420, 400_000)], 60_000),
        ("DBT-006", "منشأة", "", [(380, 600_000), (600, 500_000)], 0),
        ("DBT-007", "مستثمر", "CTR-2013", [(100, 450_000), (160, 450_000)], 40_000),
        ("DBT-008", "منشأة", "", [(190, 400_000), (330, 400_000)], 30_000),
    ]
    for debtor, dtype, cid, invs, base in big:
        src = "SRC03" if cid else "SRC05"
        per = base / len(invs)
        for days, amt in invs:
            paid = round(amt * 0.1, -3) if days > 300 else 0.0  # سداد جزئي سابق يُستبعد
            add(debtor, dtype, cid, src, days, amt, paid, "متأخر", per)
    # صغار المدينين (حملة جماعية)
    for i in range(60):
        days = int(rng.choice([100, 140, 200, 280, 400, 500]))
        amt = float(round(rng.uniform(15_000, 85_000), -2))
        src = ["SRC02", "SRC05", "SRC06", "SRC07"][i % 4]
        add(f"DBT-1{i:03d}", "فرد" if i % 3 == 0 else "منشأة", "", src, days, amt, 0.0, "متأخر", round(amt * 0.05, -2))
    # مطالبات محل نزاع
    for i, amt in enumerate([900_000, 700_000, 500_000, 300_000]):
        add(f"DBT-2{i:02d}", "مستثمر", contract_ids[20 + i], "SRC03", 300 + 50 * i, amt, 0.0, "محل نزاع", 0.0)
    # مطالبات مجدولة
    for i, amt in enumerate([500_000, 350_000, 250_000]):
        add(f"DBT-3{i:02d}", "منشأة", "", "SRC05", 200 + 30 * i, amt, amt * 0.2, "مجدول", amt * 0.15)
    # حديثة التأخير أو غير مستحقة بعد
    for i in range(30):
        amt = float(round(rng.uniform(40_000, 140_000), -2))
        add(f"DBT-4{i:02d}", "منشأة", "", ["SRC02", "SRC06"][i % 2], int(rng.integers(-20, 85)), amt, 0.0, "عادي", amt * 0.6)
    # فواتير مسددة بالكامل (يجب ألا تظهر في أي فرصة)
    for i in range(12):
        amt = float(round(rng.uniform(50_000, 300_000), -2))
        add(f"DBT-001" if i == 0 else f"DBT-5{i:02d}", "منشأة", "", "SRC02", 200, amt, amt, "عادي", 0.0)
    df = pd.DataFrame(rows, columns=RECV_COLS)
    df["data_label"] = L
    return df


# ------------------------------------------------------------------ الأداء
GDS = [("GD-A", "الإدارة العامة التجريبية (أ)", True), ("GD-B", "الإدارة العامة التجريبية (ب)", True)]
DEPTS = [
    ("D01", "GD-A", "قسم المتابعة الميدانية", 1), ("D02", "GD-A", "قسم العقود والمشتريات", 2),
    ("D03", "GD-A", "قسم الخدمات الرقمية", 3), ("D04", "GD-A", "قسم الجودة والتميز", 4),
    ("D05", "GD-A", "قسم الشؤون الإدارية", 5), ("D06", "GD-A", "قسم خدمة المستفيدين", 6),
    ("D07", "GD-B", "قسم الرخص التجريبي", 1), ("D08", "GD-B", "قسم الرقابة التجريبي", 2),
    ("D09", "GD-B", "قسم التخطيط التجريبي", 3), ("D10", "GD-B", "قسم الدعم الفني التجريبي", 4),
]
KPIS = [
    ("PLAN", "إنجاز الخطة", "نسبة المهام والمبادرات المخطط لها في الشهر التي أُنجزت فعليًا من إجمالي المخطط", "%", 50, 0, 100),
    ("TIME", "الالتزام بالوقت", "نسبة المهام والمعاملات المنجزة ضمن المدة الزمنية المعتمدة من إجمالي المنجز", "%", 30, 0, 100),
    ("QUALITY", "جودة المخرجات", "نسبة المخرجات المقبولة دون إعادة عمل وفق مراجعة الجودة من إجمالي المخرجات", "%", 20, 0, 100),
]
TARGETS = {"PLAN": 90.0, "TIME": 85.0, "QUALITY": 95.0}


def performance():
    recs = []
    months_a = [f"2026-{m:02d}" for m in range(1, 10)]
    # مستوى أساسي لكل قسم (نسبة من المستهدف) + اتجاه
    profile = {"D01": (0.95, 0.004), "D02": (0.88, -0.008), "D03": (0.90, 0.003), "D04": (0.93, 0.004), "D05": (0.80, -0.020), "D06": (0.90, -0.003)}
    final = {  # سبتمبر 2026 مصمم لإظهار كل الحالات
        "D01": {"PLAN": 88, "TIME": 84, "QUALITY": 94},
        "D02": {"PLAN": 70, "TIME": 60, "QUALITY": 90},
        "D03": {"PLAN": 86, "TIME": 83, "QUALITY": None},  # بيانات ناقصة
        "D04": {"PLAN": 92, "TIME": 80, "QUALITY": 93},     # تجاوز مستهدف الخطة لا يعوض غيره
        "D05": {"PLAN": 45, "TIME": 50, "QUALITY": 80},
        "D06": {"PLAN": 80, "TIME": 70, "QUALITY": 88},
    }
    for d, (lvl, trend) in profile.items():
        for i, m in enumerate(months_a):
            if d == "D05" and m == "2026-04":
                continue  # شهر غير مدخل بالكامل (فجوة في الاتجاه)
            for k, tgt in TARGETS.items():
                if m == "2026-09":
                    act = final[d][k]
                else:
                    act = float(np.clip(tgt * (lvl + trend * i + rng.normal(0, 0.03)), 0, 100))
                    act = round(act, 1)
                    if d == "D02" and m == "2026-08" and k == "TIME":
                        act = 0.0  # صفر فعلي (توقف نظام) وليس قيمة مفقودة
                recs.append((d, m, k, tgt, act))
    months_b = [f"2026-{m:02d}" for m in range(6, 10)]
    prof_b = {"D07": 0.97, "D08": 0.85, "D09": 0.74, "D10": 0.92}
    for d, lvl in prof_b.items():
        for m in months_b:
            if d == "D10" and m < "2026-08":
                continue  # قسم أضيف حديثًا
            for k, tgt in TARGETS.items():
                act = round(float(np.clip(tgt * (lvl + rng.normal(0, 0.03)), 0, 100)), 1)
                recs.append((d, m, k, tgt, act))
    df = pd.DataFrame(recs, columns=["dept_id", "month", "kpi_id", "target", "actual"])
    df["data_label"] = L
    return df


def main(out: Path = OUT):
    out.mkdir(parents=True, exist_ok=True)
    assets_c, contracts = contracts_and_assets()
    assets = pd.DataFrame(candidate_assets() + assets_c, columns=ASSET_COLS)
    assets["data_label"] = L
    cdf = pd.DataFrame(contracts, columns=CONTRACT_COLS)
    cdf["data_label"] = L
    tables = {
        "settings": settings(),
        "revenue_sources": sources(),
        "assets": assets,
        "contracts": cdf,
        "receivables": receivables(list(cdf["contract_id"])),
        "market_benchmarks": benchmarks(),
        "general_departments": pd.DataFrame([(g, n, a, L) for g, n, a in GDS], columns=["gd_id", "gd_name", "active", "data_label"]),
        "departments": pd.DataFrame([(d, g, n, o, True, L) for d, g, n, o in DEPTS], columns=["dept_id", "gd_id", "dept_name", "sort_order", "active", "data_label"]),
        "kpi_definitions": pd.DataFrame(KPIS, columns=["kpi_id", "kpi_name", "definition", "unit", "default_weight", "min_value", "max_value"]),
        "performance_records": performance(),
    }
    for k, df in tables.items():
        df.to_csv(out / f"{k}.csv", index=False, encoding="utf-8-sig")
    print(f"تم توليد {len(tables)} جداول في {out}")
    return tables


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
