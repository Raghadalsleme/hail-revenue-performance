"""محرك اكتشاف فرص الإيرادات — قواعد تحليلية قابلة للتفسير (لا يوجد نموذج تعلم آلة مدرب في هذا الإصدار).

كل فرصة تُستخرج من صفوف البيانات مباشرة، وتحمل: الأدلة، طريقة الحساب بالأرقام، الافتراضات،
المهلة، تاريخ بدء الأثر، السهولة والمخاطر، والموافقات المطلوبة. الاقتراح تحليلي فقط وليس
موافقة تنظيمية أو إذنًا بالتنفيذ.

نقطة توسعة لاحقة: يمكن استبدال افتراضات ثابتة (مثل نسب الاسترداد أو الإشغال المتوقع) بتقديرات
نموذج ML عبر تمرير `estimators` مخصصة إلى detect_opportunities بعد توفر بيانات تاريخية حقيقية.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .config import ENGINE_DEFAULTS, PRIORITY_WEIGHTS_DEFAULT
from .formatting import fmt_pct, fmt_sar
from .revenue_data import RevenueData

TYPE_LABELS = {
    "lease": "استثمار/تأجير أصل غير مستغل",
    "renewal": "مراجعة قيمة عقد عند التجديد",
    "collection": "تحسين تحصيل مستحقات متأخرة",
}
NATURE_LABELS = {"recurring": "إيراد متكرر", "one_time": "تحصيل لمرة واحدة"}
EASE_LABELS = {1: "صعبة جدًا", 2: "صعبة", 3: "متوسطة", 4: "سهلة", 5: "سهلة جدًا"}
RISK_LABELS = {1: "منخفضة جدًا", 2: "منخفضة", 3: "متوسطة", 4: "مرتفعة", 5: "مرتفعة جدًا"}

APPROVALS = {
    "lease_land": [
        "التحقق من الصك والحدود والاستخدام النظامي للأرض",
        "تقييم إيجاري من مقيّم معتمد",
        "اعتماد لجنة الاستثمار وصاحب الصلاحية",
        "الطرح التنافسي عبر منصة «فرص» وفق لائحة التصرف بالعقارات البلدية والأنظمة المعمول بها",
    ],
    "lease_units": [
        "التحقق من جاهزية الوحدات واشتراطات السلامة",
        "تقييم إيجاري معتمد",
        "اعتماد صاحب الصلاحية وإجراءات الطرح النظامية",
    ],
    "billboards": [
        "التحقق من اشتراطات الإعلانات التجارية والسلامة المرورية",
        "موافقة الإدارة المختصة بالتخطيط والطرق",
        "الطرح النظامي واعتماد صاحب الصلاحية",
    ],
    "renewal": [
        "مراجعة قانونية لبنود التجديد والإشعار التعاقدي",
        "تقييم إيجاري محدث من مقيّم معتمد",
        "اعتماد صاحب الصلاحية قبل التفاوض",
        "إشعار المستثمر ضمن المدة التعاقدية",
    ],
    "collection": [
        "مطابقة المطالبات مع النظام المالي والتحقق من صحتها",
        "مراجعة الإدارة القانونية قبل أي إجراء تنفيذي",
        "إشعارات نظامية للمدينين واعتماد أي جدولة سداد",
    ],
}


@dataclass(frozen=True)
class UseRule:
    key: str
    label: str
    bench_category: str
    unit: str
    lead_days: int
    grace_days: int
    ease: int
    risk: int
    approvals_key: str


def _months(days: int) -> str:
    m = days / 30.4
    return f"{days} يومًا (≈ {m:.1f} شهر)"


def candidate_uses(asset: pd.Series) -> list[UseRule]:
    """قواعد ربط خصائص الأصل بالاستخدام الاستثماري المناسب (شفافة وقابلة للتعديل)."""
    t, z = asset["asset_type"], asset["zoning"]
    uses: list[UseRule] = []
    if t == "أرض فضاء":
        if z in ("تجاري", "استثماري متعدد"):
            uses.append(UseRule("land_commercial", "طرح استثماري تجاري (تأجير أرض طويل الأجل)", "أرض تجارية", "م²", 150, 180, 2, 3, "lease_land"))
            if bool(asset["on_main_road"]) and float(asset["frontage_m"]) >= 40:
                uses.append(UseRule("billboards", "استثمار الواجهة كموقع لوحات إعلانية", "لوحة إعلانية", "لوحة", 90, 0, 3, 2, "billboards"))
        elif z == "خدمي":
            uses.append(UseRule("land_service", "استثمار خدمي (مرافق تعليمية/صحية أهلية)", "أرض خدمية", "م²", 150, 180, 2, 3, "lease_land"))
        elif z == "ترفيهي":
            uses.append(UseRule("land_seasonal", "تأجير موسمي لفعاليات وأنشطة ترفيهية", "أرض ترفيهية (موسمي)", "م²", 60, 0, 3, 3, "lease_land"))
    elif t == "محل تجاري":
        uses.append(UseRule("retail_units", "تأجير المساحات التجارية الشاغرة", "محل تجاري", "م²", 75, 0, 4, 2, "lease_units"))
    elif t == "مبنى مكاتب":
        uses.append(UseRule("office_units", "تأجير المساحات المكتبية الشاغرة", "مكاتب", "م²", 90, 0, 3, 2, "lease_units"))
    elif t == "كشك":
        uses.append(UseRule("kiosk", "تأجير الكشك لنشاط تجاري خفيف", "كشك", "م²", 45, 0, 4, 1, "lease_units"))
    return uses


def bench_category_for_asset(asset: pd.Series) -> str | None:
    t, z = asset["asset_type"], asset["zoning"]
    if t == "أرض فضاء":
        return {"تجاري": "أرض تجارية", "استثماري متعدد": "أرض تجارية", "خدمي": "أرض خدمية", "ترفيهي": "أرض ترفيهية (موسمي)"}.get(z)
    return {"محل تجاري": "محل تجاري", "مبنى مكاتب": "مكاتب", "كشك": "كشك"}.get(t)


def in_year_window(effective: date, year_end: date, days_in_year: int) -> tuple[int, float]:
    """الأيام الواقعة ضمن السنة من تاريخ بدء الأثر حتى 31 ديسمبر (شاملة) ونسبتها من السنة."""
    if effective > year_end:
        return 0, 0.0
    days = (year_end - effective).days + 1
    return days, days / days_in_year


def count_invoices(n: int) -> str:
    """صيغة العدد العربية المبسطة للفواتير."""
    if n == 1:
        return "فاتورة واحدة"
    if n == 2:
        return "فاتورتان"
    if 3 <= n <= 10:
        return f"{n} فواتير"
    return f"{n} فاتورة"


def _bucket(days_overdue: int) -> str:
    if days_overdue <= 180:
        return "90-180"
    if days_overdue <= 365:
        return "181-365"
    return "365+"


BUCKET_LABELS = {"90-180": "90–180 يومًا", "181-365": "181–365 يومًا", "365+": "أكثر من سنة"}


# ------------------------------------------------------------------ تقدير القيم لأي معامل حساسية
def estimate(opp: dict | pd.Series, m: float = 1.0) -> dict:
    """يعيد القيم المعدلة بمعامل الحساسية m مع تطبيق السقوف المنطقية.

    - التأجير: m يُطبّق على نسبة الإشغال المتوقعة بسقف إشغال كامل 100%.
    - التجديد: m يُطبّق على الزيادة بسقف (الحد الأعلى للنطاق المرجعي أو السقف التعاقدي).
    - التحصيل: m يُطبّق على نسب الاسترداد بسقف 100% وبسقف الرصيد غير المحصل، ثم يُطرح التحصيل المتوقع أصلًا.
    """
    c = opp["calc"]
    t = opp["opp_type"]
    capped = False
    if t == "lease":
        occ = c["occ"] * m
        if occ > 1.0:
            occ, capped = 1.0, True
        annual = max(0.0, c["qty"] * c["rate"] * occ - c["current"])
        in_year = annual * c["fraction"]
        return {"annual": annual, "in_year": in_year, "capped": capped, "one_time_total": 0.0}
    if t == "renewal":
        uplift = c["uplift"] * m
        if uplift > c["cap_annual"]:
            uplift, capped = c["cap_annual"], True
        annual = max(0.0, uplift)
        return {"annual": annual, "in_year": annual * c["fraction"], "capped": capped, "one_time_total": 0.0}
    if t == "collection":
        gross_full = 0.0
        for out_b, r_b in c["buckets"]:
            r = r_b * m
            if r > 1.0:
                r, capped = 1.0, True
            gross_full += out_b * r
        if gross_full > c["outstanding"]:
            gross_full, capped = c["outstanding"], True
        gross_in_year = min(gross_full * c["time_factor"], c["outstanding"])
        in_year = max(0.0, gross_in_year - c["baseline"])
        total = max(0.0, gross_full - c["baseline"])
        return {"annual": 0.0, "in_year": in_year, "capped": capped, "one_time_total": total}
    raise ValueError(t)


# ------------------------------------------------------------------ المحرك
def detect_opportunities(data: RevenueData, params: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """يعيد (الفرص، المستبعد مع الأسباب)."""
    p = {**ENGINE_DEFAULTS, **(params or {})}
    s = data.settings
    snap, ye, diy = s.snapshot_date, s.year_end, s.days_in_year
    opps: list[dict] = []
    excluded: list[dict] = []

    bench = data.benchmarks.set_index(["category", "location_tier"])

    def find_bench(cat, tier):
        try:
            return bench.loc[(cat, tier)]
        except KeyError:
            return None

    active_contract_assets = set(data.contracts.loc[data.contracts["status"] == "ساري", "asset_id"])

    # ---------------- 1) الأصول غير المستغلة
    for _, a in data.assets.iterrows():
        aid = a["asset_id"]
        if bool(a["restricted"]):
            excluded.append({"المرجع": aid, "النوع": "أصل", "السبب": f"أصل مقيد: {a['restriction_reason'] or 'سبب غير مذكور'}"})
            continue
        if a["status"] == "مستغل" or float(a["current_occupancy"]) >= 0.95:
            if aid in active_contract_assets:
                continue  # مؤجر بعقد ساري — يُقيَّم في فرص التجديد
            excluded.append({"المرجع": aid, "النوع": "أصل", "السبب": "مستغل بالكامل وفق البيانات"})
            continue
        uses = candidate_uses(a)
        if not uses:
            excluded.append({"المرجع": aid, "النوع": "أصل", "السبب": f"الاستخدام النظامي «{a['zoning']}» لا يتوافق مع الاستخدامات الاستثمارية المعرّفة في القواعد"})
            continue
        made = 0
        for u in uses:
            b = find_bench(u.bench_category, a["location_tier"])
            if b is None:
                excluded.append({"المرجع": aid, "النوع": "أصل", "السبب": f"لا يتوفر مرجع سوقي لفئة «{u.bench_category}» في فئة الموقع {a['location_tier']} ({u.label})"})
                continue
            if u.unit == "لوحة":
                qty = float(min(4, int(float(a["frontage_m"]) // 40)))
                current = 0.0  # لا يوجد إيراد إعلاني حالي على الأصل
                qty_txt = f"{qty:.0f} لوحة (واجهة {float(a['frontage_m']):.0f} م ÷ 40 م، بحد أقصى 4)"
            else:
                qty = float(a["area_sqm"])
                current = float(a["current_annual_revenue_sar"])
                qty_txt = f"{qty:,.0f} م²"
            rate = float(b["ref_annual_rate_sar"])
            occ = float(b["expected_occupancy"])
            lead, grace, ease, risk = u.lead_days, u.grace_days, u.ease, u.risk
            assumptions = [
                f"معدل الإيجار المرجعي {rate:,.0f} ريال/{u.unit}/سنة (مرجع {b['benchmark_id']} بتاريخ {pd.Timestamp(b['as_of_date']).date().isoformat()})",
                f"نسبة الإشغال/الاستخدام المتوقعة {fmt_pct(occ * 100, 0)} وفق المرجع",
                f"مهلة الطرح والترسية {_months(lead)}",
            ]
            if grace:
                assumptions.append(f"فترة تجهيز وإنشاء معفاة من الأجرة {_months(grace)} (ممارسة شائعة في عقود الأراضي — افتراض)")
            if not bool(a["utilities_available"]) and u.unit != "لوحة":
                lead += p["no_utilities_extra_days"]
                ease = max(1, ease - 1)
                risk = min(5, risk + 1)
                assumptions.append(f"الخدمات غير متوفرة: أُضيفت مهلة {p['no_utilities_extra_days']} يومًا وخُفضت السهولة ورُفعت المخاطر")
            assumptions.append("الإيراد محسوب قبل خصم أي تكاليف تنفيذ أو تشغيل — إيراد وليس ربحًا")
            full = qty * rate
            expected = full * occ
            annual = expected - current
            if annual <= 0:
                excluded.append({"المرجع": aid, "النوع": "أصل", "السبب": f"الإيراد الحالي ({fmt_sar(current)}) يعادل التقدير المرجعي أو يزيد عليه ({u.label})"})
                continue
            effective = snap + timedelta(days=lead + grace + 1)
            days, frac = in_year_window(effective, ye, diy)
            calc = {"qty": qty, "rate": rate, "occ": occ, "current": current, "fraction": frac}
            method = (
                "الإيراد السنوي المحتمل (ريال) = الكمية × المعدل المرجعي × الإشغال المتوقع − الإيراد الحالي المدرج\n"
                f"{qty:,.0f} × {rate:,.0f} × {occ:.2f} − {current:,.0f} = {annual:,.0f}\n"
                f"المساهمة حتى نهاية السنة (ريال) = الإيراد السنوي × (أيام التشغيل ضمن السنة ÷ أيام السنة)، بدءًا من {effective.isoformat()}\n"
                f"{annual:,.0f} × ({days} ÷ {diy}) = {annual * frac:,.0f}"
            )
            reason = f"{a['asset_type']} «{a['asset_name']}» بحالة «{a['status']}» (إشغال حالي {fmt_pct(float(a['current_occupancy']) * 100, 0)}) واستخدام نظامي «{a['zoning']}»"
            if bool(a["on_main_road"]):
                reason += " ويطل على شارع رئيسي"
            evidence = [
                ("الأصل", f"{aid} — {a['asset_name']} ({a['district']})"),
                ("النوع / الاستخدام النظامي", f"{a['asset_type']} / {a['zoning']}"),
                ("المساحة", f"{float(a['area_sqm']):,.0f} م²"),
                ("الواجهة / شارع رئيسي", f"{float(a['frontage_m']):,.0f} م / {'نعم' if bool(a['on_main_road']) else 'لا'}"),
                ("الخدمات", "متوفرة" if bool(a["utilities_available"]) else "غير متوفرة"),
                ("الإشغال الحالي", fmt_pct(float(a["current_occupancy"]) * 100, 0)),
                ("الإيراد الحالي المدرج في الأساس", fmt_sar(current)),
                ("الكمية المستخدمة في الحساب", qty_txt),
                ("المرجع السوقي", f"{b['benchmark_id']}: {rate:,.0f} ريال/{u.unit}/سنة (الحد الأعلى {float(b['upper_annual_rate_sar']):,.0f})"),
            ]
            made += 1
            opps.append({
                "opp_id": f"LSE-{aid}-{made}",
                "opp_type": "lease",
                "ref_type": "أصل",
                "ref_ids": aid,
                "ref_display": f"أصل {aid}",
                "title": f"{u.label} — {a['asset_name']}",
                "use_key": u.key,
                "reason": reason,
                "evidence": evidence,
                "method": method,
                "assumptions": assumptions,
                "approvals": APPROVALS[u.approvals_key],
                "lead_days": lead + grace,
                "effective_date": effective,
                "in_year_days": days,
                "nature": "recurring",
                "ease": ease,
                "risk": risk,
                "conflict_group": f"ASSET:{aid}",
                "calc": calc,
                "cap_note": "سقف الإشغال الكامل 100%",
            })

    # ---------------- 2) العقود القريبة من التجديد
    assets_idx = data.assets.set_index("asset_id")
    window_end = snap + timedelta(days=int(p["renewal_window_days"]))
    for _, c in data.contracts.iterrows():
        cid = c["contract_id"]
        end = pd.Timestamp(c["end_date"]).date()
        if c["status"] != "ساري":
            continue
        if end <= snap:
            excluded.append({"المرجع": cid, "النوع": "عقد", "السبب": "عقد ساري بتاريخ نهاية سابق لتاريخ اللقطة — يحتاج تصحيح البيانات"})
            continue
        if end > window_end:
            continue  # ليس قريبًا من التجديد
        if bool(c["in_dispute"]):
            excluded.append({"المرجع": cid, "النوع": "عقد", "السبب": "عقد محل نزاع — تُستبعد مراجعة القيمة حتى حسم النزاع"})
            continue
        if not bool(c["renegotiable"]):
            excluded.append({"المرجع": cid, "النوع": "عقد", "السبب": "شروط العقد لا تسمح بمراجعة القيمة عند التجديد (وفق البيانات)"})
            continue
        a = assets_idx.loc[c["asset_id"]]
        cat = bench_category_for_asset(a)
        b = find_bench(cat, a["location_tier"]) if cat else None
        if b is None:
            excluded.append({"المرجع": cid, "النوع": "عقد", "السبب": f"لا يتوفر مرجع سوقي لفئة الأصل ({cat}) في فئة الموقع {a['location_tier']}"})
            continue
        area = float(c["leased_area_sqm"])
        cur = float(c["annual_value_sar"])
        ref = float(b["ref_annual_rate_sar"])
        upper = float(b["upper_annual_rate_sar"])
        cur_rate = cur / area
        below = 1 - cur_rate / ref
        if below < p["underpricing_threshold"]:
            excluded.append({"المرجع": cid, "النوع": "عقد", "السبب": f"القيمة الحالية ضمن نطاق المرجع (الفرق {fmt_pct(max(below, 0) * 100)} أقل من حد {fmt_pct(p['underpricing_threshold'] * 100, 0)})"})
            continue
        uplift_ref = area * ref - cur
        cap_annual = area * upper - cur
        pct = c["max_renewal_increase_pct"]
        has_cap = pct is not None and not (isinstance(pct, float) and np.isnan(pct))
        uplift = uplift_ref
        cap_label = "الحد الأعلى للنطاق المرجعي"
        cap_expr = f"{area:,.0f} × {upper:,.0f} − {cur:,.0f} = {cap_annual:,.0f}"
        if has_cap:
            contractual = cur * float(pct)
            uplift = min(uplift_ref, contractual)
            cap_annual = min(cap_annual, contractual)
            cap_label = f"السقف التعاقدي للزيادة {fmt_pct(float(pct) * 100, 0)}"
            cap_expr = f"min({area * upper - cur:,.0f} , {cur:,.0f} × {float(pct):.2f}) = {cap_annual:,.0f}"
        renewal_date = end + timedelta(days=1)
        ready = snap + timedelta(days=int(p["renewal_lead_days"]) + 1)
        effective = max(renewal_date, ready)
        days, frac = in_year_window(effective, ye, diy)
        ease = 4 if has_cap else 3
        risk = 2
        assumptions = [
            f"القيمة المستهدفة عند التجديد = المساحة × المعدل المرجعي ({ref:,.0f} ريال/م²/سنة، مرجع {b['benchmark_id']})",
            f"لا يُحتسب أي أثر قبل تاريخ التجديد ({renewal_date.isoformat()})",
            f"مهلة إعداد المراجعة والتفاوض والاعتماد {_months(int(p['renewal_lead_days']))}",
            "يُفترض تجديد المستثمر الحالي بالقيمة المراجعة",
            "الإيراد محسوب قبل خصم أي تكاليف — إيراد وليس ربحًا",
        ]
        if ready > renewal_date:
            assumptions.append("المراجعة لا تكتمل قبل تاريخ التجديد؛ يُفترض تمديد مؤقت بالقيمة الحالية حتى اكتمالها")
        if uplift / cur > 0.30:
            risk = 3
            assumptions.append("الزيادة تتجاوز 30% من القيمة الحالية: مخاطر عدم تجديد المستثمر أعلى")
        method = (
            "الزيادة السنوية (ريال) = (المساحة × المعدل المرجعي) − القيمة الحالية\n"
            f"({area:,.0f} × {ref:,.0f}) − {cur:,.0f} = {uplift_ref:,.0f}\n"
            + (f"بعد تطبيق السقف التعاقدي للزيادة ({float(pct):.0%}):\nmin({uplift_ref:,.0f} , {cur:,.0f} × {float(pct):.2f}) = {uplift:,.0f}\n" if has_cap and uplift < uplift_ref else "")
            + f"المساهمة حتى نهاية السنة (ريال) من تاريخ بدء الأثر {effective.isoformat()}:\n"
            f"{uplift:,.0f} × ({days} ÷ {diy}) = {uplift * frac:,.0f}\n"
            f"السقف المستخدم في السيناريوهات — {cap_label}:\n{cap_expr}"
        )
        evidence = [
            ("العقد", f"{cid} — {c['activity']} (المستثمر {c['investor_ref']})"),
            ("الأصل", f"{c['asset_id']} — {a['asset_name']} ({a['district']})"),
            ("تاريخ النهاية", end.isoformat()),
            ("القيمة السنوية الحالية", fmt_sar(cur)),
            ("المساحة المؤجرة", f"{area:,.0f} م²"),
            ("المعدل الحالي", f"{cur_rate:,.0f} ريال/م²/سنة"),
            ("المعدل المرجعي", f"{ref:,.0f} ريال/م²/سنة ({b['benchmark_id']})"),
            ("الفرق عن المرجع", fmt_pct(below * 100)),
            ("السقف التعاقدي للزيادة", fmt_pct(float(pct) * 100, 0) if has_cap else "لا يوجد"),
        ]
        opps.append({
            "opp_id": f"RNW-{cid}",
            "opp_type": "renewal",
            "ref_type": "عقد",
            "ref_ids": cid,
            "ref_display": f"عقد {cid} · أصل {c['asset_id']}",
            "title": f"مراجعة قيمة العقد {cid} عند التجديد — {a['asset_name']}",
            "use_key": "renewal",
            "reason": f"العقد ينتهي في {end.isoformat()} (خلال {(end - snap).days} يومًا من تاريخ اللقطة) وقيمته أقل من المرجع السوقي بنسبة {fmt_pct(below * 100)}",
            "evidence": evidence,
            "method": method,
            "assumptions": assumptions,
            "approvals": APPROVALS["renewal"],
            "lead_days": int(p["renewal_lead_days"]),
            "effective_date": effective,
            "in_year_days": days,
            "nature": "recurring",
            "ease": ease,
            "risk": risk,
            "conflict_group": f"ASSET:{c['asset_id']}",
            "calc": {"uplift": uplift, "cap_annual": max(cap_annual, 0.0), "fraction": frac},
            "cap_note": "سقف تعاقدي" if has_cap else "سقف الحد الأعلى للنطاق المرجعي",
        })

    # ---------------- 3) المستحقات المتأخرة
    r = data.receivables.copy()
    r["outstanding"] = r["amount_due_sar"] - r["amount_paid_sar"]
    r = r[r["outstanding"] > 0.005].copy()
    r["days_overdue"] = (pd.Timestamp(snap) - r["due_date"]).dt.days
    groups = [
        (r["status"] == "محل نزاع", "مطالبات محل نزاع — لا تُحتسب حتى حسم النزاع"),
        ((r["status"] == "مجدول") & (r["status"] != "محل نزاع"), "مطالبات مجدولة باتفاق سداد قائم — تحصيلها ضمن الأساس"),
    ]
    mask_excl = pd.Series(False, index=r.index)
    for m, reason in groups:
        m = m & ~mask_excl
        if m.any():
            excluded.append({"المرجع": count_invoices(int(m.sum())), "النوع": "فواتير", "السبب": f"{reason} (رصيد {fmt_sar(r.loc[m, 'outstanding'].sum())})"})
        mask_excl |= m
    young = (~mask_excl) & (r["days_overdue"] < p["min_overdue_days"])
    if young.any():
        excluded.append({"المرجع": count_invoices(int(young.sum())), "النوع": "فواتير", "السبب": f"تأخير أقل من {p['min_overdue_days']} يومًا أو غير مستحقة بعد — تُتابع ضمن التحصيل الاعتيادي (رصيد {fmt_sar(r.loc[young, 'outstanding'].sum())})"})
    mask_excl |= young
    elig = r[~mask_excl].copy()
    if not elig.empty:
        elig["bucket"] = elig["days_overdue"].map(_bucket)
        rates = p["recovery_rates"]
        start = snap + timedelta(days=int(p["collection_lead_days"]) + 1)
        avail_days, _ = in_year_window(start, ye, diy)
        tf = min(1.0, avail_days / float(p["collection_campaign_days"]))
        totals = elig.groupby("debtor_id")["outstanding"].sum()
        small = set(totals[totals < p["pool_threshold_sar"]].index)
        elig["group"] = elig["debtor_id"].where(~elig["debtor_id"].isin(small), "POOL")
        for gid, g in elig.groupby("group", sort=True):
            outstanding = float(g["outstanding"].sum())
            baseline = float(g["expected_baseline_collection_sar"].sum())
            buckets = []
            bucket_txt = []
            for bk in ("90-180", "181-365", "365+"):
                ob = float(g.loc[g["bucket"] == bk, "outstanding"].sum())
                if ob > 0:
                    buckets.append((ob, float(rates[bk])))
                    bucket_txt.append(f"{ob:,.0f} × {rates[bk]:.2f}")
            calc = {"buckets": buckets, "outstanding": outstanding, "baseline": baseline, "time_factor": tf}
            est = estimate({"opp_type": "collection", "calc": calc}, 1.0)
            if est["one_time_total"] <= 0:
                excluded.append({"المرجع": gid, "النوع": "مدين", "السبب": "التحصيل المتوقع أصلًا يغطي الاسترداد المقدّر — لا توجد زيادة"})
                continue
            old_share = float(g.loc[g["bucket"] == "365+", "outstanding"].sum()) / outstanding
            mid_share = float(g.loc[g["bucket"] == "181-365", "outstanding"].sum()) / outstanding
            if old_share > 0.5:
                ease, risk = 2, 4
            elif old_share + mid_share > 0.5:
                ease, risk = 3, 3
            else:
                ease, risk = 4, 2
            gross_full = sum(o * rr for o, rr in buckets)
            inv = list(g["invoice_id"])
            inv_txt = "، ".join(inv[:5]) + (f" (+{len(inv) - 5})" if len(inv) > 5 else "")
            is_pool = gid == "POOL"
            title = (
                f"حملة تحصيل جماعية لصغار المدينين ({g['debtor_id'].nunique()} مدينًا)"
                if is_pool else f"خطة تحصيل مستحقات المدين {gid} ({g['debtor_type'].iloc[0]})"
            )
            cd = int(p["collection_campaign_days"])
            tf_expr = f"({avail_days} ÷ {cd})" if avail_days < cd else "1"
            method = (
                "الاسترداد المقدّر خلال الحملة (ريال) = مجموع (الرصيد غير المحصل × نسبة الاسترداد حسب عمر الدين)\n"
                f"{' + '.join(bucket_txt)} = {gross_full:,.0f}\n"
                f"معامل الوقت المتاح = الأصغر من 1 و(الأيام المتاحة حتى نهاية السنة {avail_days} ÷ مدة الحملة {cd})\n"
                f"min(1 , {avail_days} ÷ {cd}) = {tf:.4f}\n"
                f"المساهمة حتى نهاية السنة (ريال) = الاسترداد × معامل الوقت − التحصيل المتوقع أصلًا\n"
                f"{gross_full:,.0f} × {tf_expr} − {baseline:,.0f} = {est['in_year']:,.0f}\n"
                "السقف = الرصيد غير المحصل − التحصيل المتوقع أصلًا\n"
                f"{outstanding:,.0f} − {baseline:,.0f} = {outstanding - baseline:,.0f}"
            )
            evidence = [
                ("المدين/المجموعة", "صغار المدينين (أرصدة أقل من " + fmt_sar(p["pool_threshold_sar"]) + ")" if is_pool else gid),
                ("الفواتير", f"{count_invoices(len(inv))}: {inv_txt}"),
                ("المستحق الإجمالي", fmt_sar(float(g["amount_due_sar"].sum()))),
                ("المسدد سابقًا (مستبعد)", fmt_sar(float(g["amount_paid_sar"].sum()))),
                ("الرصيد غير المحصل", fmt_sar(outstanding)),
                ("التوزيع حسب عمر الدين", " | ".join(f"{BUCKET_LABELS[bk]}: {fmt_sar(float(g.loc[g['bucket'] == bk, 'outstanding'].sum()))}" for bk in ("90-180", "181-365", "365+") if (g["bucket"] == bk).any())),
                ("التحصيل المتوقع أصلًا (ضمن الأساس)", fmt_sar(baseline)),
                ("أقدم تأخير", f"{int(g['days_overdue'].max())} يومًا"),
            ]
            assumptions = [
                "نسب الاسترداد خلال الحملة: " + "، ".join(f"{BUCKET_LABELS[k]} {v:.0%}" for k, v in rates.items()) + " (افتراضات تحتاج معايرة ببيانات تحصيل تاريخية)",
                f"مدة الحملة المرجعية {int(p['collection_campaign_days'])} يومًا ومهلة البدء {int(p['collection_lead_days'])} يومًا",
                "المبالغ المسددة سابقًا مستبعدة بالكامل، ويُطرح التحصيل المتوقع أصلًا لتجنب الازدواج",
                "تحصيل نقدي لمرة واحدة وليس إيرادًا متكررًا",
                "على أساس الاستحقاق: هذه الذمم أُثبتت سابقًا كإيراد، فتحصيلها يحسّن النقد ولا يُعد إيرادًا جديدًا",
            ]
            opps.append({
                "opp_id": f"COL-{gid}",
                "opp_type": "collection",
                "ref_type": "فواتير",
                "ref_ids": ", ".join(inv),
                "ref_display": f"{'صغار المدينين' if is_pool else 'المدين ' + gid} · {count_invoices(len(inv))}",
                "title": title,
                "use_key": "collection",
                "reason": f"رصيد غير محصل {fmt_sar(outstanding)} متأخر {int(p['min_overdue_days'])} يومًا فأكثر وغير محل نزاع أو جدولة",
                "evidence": evidence,
                "method": method,
                "assumptions": assumptions,
                "approvals": APPROVALS["collection"],
                "lead_days": int(p["collection_lead_days"]),
                "effective_date": start,
                "in_year_days": avail_days,
                "nature": "one_time",
                "ease": ease,
                "risk": risk,
                "conflict_group": f"DEBT:{gid}",
                "calc": calc,
                "cap_note": "سقف الرصيد غير المحصل",
            })

    cols = ["opp_id", "opp_type", "ref_type", "ref_ids", "ref_display", "title", "use_key", "reason", "evidence", "method", "assumptions",
            "approvals", "lead_days", "effective_date", "in_year_days", "nature", "ease", "risk", "conflict_group", "calc", "cap_note"]
    df = pd.DataFrame(opps, columns=cols)
    ex = pd.DataFrame(excluded, columns=["المرجع", "النوع", "السبب"])
    if df.empty:
        for c in ("annual_potential", "in_year", "one_time_total", "priority_score", "rank"):
            df[c] = pd.Series(dtype=float)
        df["type_label"] = pd.Series(dtype=str)
        df["nature_label"] = pd.Series(dtype=str)
        return df, ex
    base = df.apply(lambda row: estimate(row, 1.0), axis=1)
    df["annual_potential"] = [b["annual"] for b in base]
    df["in_year"] = [b["in_year"] for b in base]
    df["one_time_total"] = [b["one_time_total"] for b in base]
    df["type_label"] = df["opp_type"].map(TYPE_LABELS)
    df["nature_label"] = df["nature"].map(NATURE_LABELS)
    df = score_priority(df, PRIORITY_WEIGHTS_DEFAULT)
    return df, ex


def score_priority(df: pd.DataFrame, weights: dict) -> pd.DataFrame:
    """درجة أولوية نسبية من 0 إلى 100 — ليست احتمال نجاح.

    الدرجة = (و1 × مساهمة السنة المعيارية + و2 × السهولة المعيارية + و3 × (عكس المخاطر)) ÷ (و1+و2+و3)
    - مساهمة السنة المعيارية = مساهمة الفرصة حتى نهاية السنة ÷ أعلى مساهمة بين الفرص × 100
    - السهولة المعيارية = (السهولة − 1) ÷ 4 × 100
    - عكس المخاطر = (5 − المخاطر) ÷ 4 × 100
    """
    df = df.copy()
    if df.empty:
        df["priority_score"] = pd.Series(dtype=float)
        df["rank"] = pd.Series(dtype=int)
        return df
    w = {k: max(0.0, float(weights.get(k, 0))) for k in ("contribution", "ease", "risk")}
    tot = sum(w.values()) or 1.0
    mx = float(df["in_year"].max())
    c = df["in_year"] / mx * 100 if mx > 0 else pd.Series(0.0, index=df.index)
    e = (df["ease"].astype(float) - 1) / 4 * 100
    rk = (5 - df["risk"].astype(float)) / 4 * 100
    df["score_contribution"] = c
    df["score_ease"] = e
    df["score_risk"] = rk
    df["priority_score"] = ((w["contribution"] * c + w["ease"] * e + w["risk"] * rk) / tot).round(1)
    df = df.sort_values(["priority_score", "in_year", "annual_potential"], ascending=[False, False, False]).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df) + 1)
    return df
