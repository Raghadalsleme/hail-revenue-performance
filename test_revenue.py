"""الفجوة ونسبة الإنجاز والفائض، وتقديرات التأجير والتجديد والتحصيل، وأثر المهلة ونهاية السنة."""
from __future__ import annotations

import math
from datetime import date

import pytest

from core.config import ENGINE_DEFAULTS
from core.opportunities import detect_opportunities, estimate
from core.revenue import compute_kpis
from tests.conftest import days, make_data


# ------------------------------------------------------------------ الفجوة
def test_gap_and_attainment_synthetic(rev):
    k = compute_kpis(rev)
    assert k["target"] == 100_000_000
    assert k["realized"] == 80_000_000
    assert k["gap_to_date"] == 20_000_000
    assert k["attainment_pct"] == pytest.approx(80.0)
    assert k["baseline_remaining"] == 11_500_000
    assert k["projected_gap"] == 8_500_000
    assert k["surplus_to_date"] == 0


def test_surplus_when_realized_exceeds_target():
    k = compute_kpis(make_data(target=100, realized=130, baseline=5))
    assert k["gap_to_date"] == 0
    assert k["surplus_to_date"] == 30
    assert k["attainment_pct"] == pytest.approx(130.0)
    assert k["projected_gap"] == 0 and k["projected_surplus"] == 35


def test_zero_target_has_no_attainment_and_no_gap():
    k = compute_kpis(make_data(target=0, realized=50, baseline=0))
    assert k["attainment_pct"] is None
    assert k["gap_to_date"] == 0
    assert k["surplus_to_date"] == 50
    assert k["projected_attainment_pct"] is None


def test_remaining_days_and_year_end():
    d = make_data(snapshot="2026-09-30")
    assert d.settings.remaining_days == 92
    assert make_data(snapshot="2026-12-31").settings.remaining_days == 0


# ------------------------------------------------------------------ التأجير
SHOP = ("S1", "محلات", "محل تجاري", "x", "A", "تجاري", 1000, 30, True, True, "مستغل جزئيًا", 0.2, 200_000, False, "")


def test_lease_estimate_subtracts_current_revenue_and_respects_lead_time():
    data = make_data(assets=[SHOP])
    opps, _ = detect_opportunities(data)
    o = opps.set_index("opp_id").loc["LSE-S1-1"]
    annual = 1000 * 1000 * 0.9 - 200_000  # 700,000
    assert o["annual_potential"] == pytest.approx(annual)
    # مهلة 75 يومًا من 30 سبتمبر => بدء الأثر 15 ديسمبر
    assert o["effective_date"] == date(2026, 12, 15)
    assert o["in_year_days"] == days("2026-12-15", "2026-12-31") == 17
    assert o["in_year"] == pytest.approx(annual * 17 / 365)
    assert o["nature"] == "recurring"


def test_lease_land_with_grace_period_has_no_in_year_effect():
    land = ("L1", "أرض", "أرض فضاء", "x", "A", "تجاري", 5000, 20, False, True, "غير مستغل", 0, 0, False, "")
    opps, _ = detect_opportunities(make_data(assets=[land]))
    o = opps.set_index("opp_id").loc["LSE-L1-1"]
    assert o["annual_potential"] == pytest.approx(5000 * 100 * 0.9)
    assert o["in_year"] == 0  # مهلة 150 + تجهيز 180 يومًا تتجاوز نهاية السنة


def test_earlier_snapshot_increases_in_year_contribution():
    late = detect_opportunities(make_data(assets=[SHOP], snapshot="2026-09-30"))[0].set_index("opp_id").loc["LSE-S1-1", "in_year"]
    early = detect_opportunities(make_data(assets=[SHOP], snapshot="2026-03-31"))[0].set_index("opp_id").loc["LSE-S1-1", "in_year"]
    assert early > late > 0
    assert early == pytest.approx(700_000 * days("2026-06-15", "2026-12-31") / 365)


def test_snapshot_at_year_end_gives_zero_in_year():
    opps, _ = detect_opportunities(make_data(assets=[SHOP], snapshot="2026-12-31"))
    assert (opps["in_year"] == 0).all()
    assert opps.set_index("opp_id").loc["LSE-S1-1", "annual_potential"] > 0


def test_restricted_residential_and_missing_benchmark_are_excluded():
    assets = [
        ("R1", "مقيد", "أرض فضاء", "x", "A", "تجاري", 1000, 10, False, True, "غير مستغل", 0, 0, True, "نزاع"),
        ("R2", "سكني", "أرض فضاء", "x", "A", "سكني", 1000, 10, False, True, "غير مستغل", 0, 0, False, ""),
        ("R3", "بلا مرجع", "أرض فضاء", "x", "B", "تجاري", 1000, 10, False, True, "غير مستغل", 0, 0, False, ""),
    ]
    opps, ex = detect_opportunities(make_data(assets=assets))
    assert not opps["opp_id"].str.contains("R1|R2|R3").any()
    reasons = dict(zip(ex["المرجع"], ex["السبب"]))
    assert "مقيد" in reasons["R1"] and "سكني" in reasons["R2"] and "مرجع" in reasons["R3"]


def test_billboard_alternative_conflicts_with_land_lease():
    land = ("L2", "أرض واجهة", "أرض فضاء", "x", "A", "تجاري", 3000, 100, True, True, "غير مستغل", 0, 0, False, "")
    opps, _ = detect_opportunities(make_data(assets=[land]))
    sub = opps[opps["ref_ids"] == "L2"]
    assert len(sub) == 2 and sub["conflict_group"].nunique() == 1
    bb = sub[sub["use_key"] == "billboards"].iloc[0]
    assert bb["calc"]["qty"] == 2  # 100 م ÷ 40 = 2 لوحة
    assert bb["annual_potential"] == pytest.approx(2 * 100_000 * 0.8)


# ------------------------------------------------------------------ التجديد
def contract(cid, end, value, area=100, reneg=True, cap=None, dispute=False):
    return (cid, "A0", "SRC01", "INV-X", "نشاط", "2021-01-01", end, area, value, reneg, cap, dispute, "ساري")


def test_renewal_uplift_counts_only_after_renewal_date():
    data = make_data(contracts=[contract("C1", "2026-11-30", 60_000)])  # المرجع 1000 × 100 = 100,000
    o = detect_opportunities(data)[0].set_index("opp_id").loc["RNW-C1"]
    assert o["annual_potential"] == pytest.approx(40_000)
    assert o["effective_date"] == date(2026, 12, 1)
    assert o["in_year"] == pytest.approx(40_000 * 31 / 365)


def test_renewal_contractual_cap_applies():
    o = detect_opportunities(make_data(contracts=[contract("C2", "2026-11-30", 60_000, cap=0.2)]))[0].set_index("opp_id").loc["RNW-C2"]
    assert o["annual_potential"] == pytest.approx(12_000)  # 20% × 60,000
    assert estimate(o, 1.2)["annual"] == pytest.approx(12_000)  # لا يتجاوز السقف التعاقدي
    assert estimate(o, 1.2)["capped"]


def test_renewal_next_year_has_zero_in_year_but_annual_value():
    o = detect_opportunities(make_data(contracts=[contract("C3", "2027-03-31", 60_000)]))[0].set_index("opp_id").loc["RNW-C3"]
    assert o["in_year"] == 0 and o["annual_potential"] == pytest.approx(40_000)


def test_renewal_review_lead_delays_effect_when_renewal_is_too_soon():
    o = detect_opportunities(make_data(contracts=[contract("C4", "2026-10-10", 60_000)]))[0].set_index("opp_id").loc["RNW-C4"]
    assert o["effective_date"] == date(2026, 11, 15)  # 30 سبتمبر + 45 + 1


def test_renewal_exclusions():
    cs = [contract("C5", "2026-11-30", 95_000), contract("C6", "2026-11-30", 60_000, reneg=False),
          contract("C7", "2026-11-30", 60_000, dispute=True), contract("C8", "2028-01-31", 60_000)]
    opps, ex = detect_opportunities(make_data(contracts=cs))
    assert not opps["opp_id"].isin(["RNW-C5", "RNW-C6", "RNW-C7", "RNW-C8"]).any()
    refs = set(ex["المرجع"])
    assert {"C5", "C6", "C7"} <= refs and "C8" not in refs  # البعيد عن التجديد لا يُعرض كمستبعد


# ------------------------------------------------------------------ التحصيل
def inv(iid, debtor, days_overdue, due, paid=0, status="متأخر", baseline=0):
    from datetime import timedelta
    d = date(2026, 9, 30) - timedelta(days=days_overdue)
    return (iid, debtor, "منشأة", "", "SRC01", (d - timedelta(days=30)).isoformat(), d.isoformat(), due, paid, status, baseline)


def test_collection_subtracts_paid_and_baseline_and_applies_time_factor():
    rec = [inv("I1", "D1", 120, 1_000_000, paid=200_000, baseline=50_000), inv("I2", "D1", 400, 500_000)]
    o = detect_opportunities(make_data(receivables=rec))[0].set_index("opp_id").loc["COL-D1"]
    outstanding_90 = 800_000
    gross = outstanding_90 * 0.5 + 500_000 * 0.2  # 500,000
    avail = days("2026-10-16", "2026-12-31")  # مهلة 15 يومًا
    tf = min(1, avail / ENGINE_DEFAULTS["collection_campaign_days"])
    assert o["in_year"] == pytest.approx(gross * tf - 50_000)
    assert o["one_time_total"] == pytest.approx(gross - 50_000)
    assert o["nature"] == "one_time" and o["annual_potential"] == 0


def test_collection_cap_is_outstanding_balance():
    o = detect_opportunities(make_data(receivables=[inv("I3", "D2", 120, 1_000_000)]))[0].set_index("opp_id").loc["COL-D2"]
    e = estimate(o, 5.0)  # معامل مبالغ فيه
    assert e["capped"]
    assert e["one_time_total"] <= 1_000_000
    assert e["in_year"] <= 1_000_000


def test_collection_exclusions_disputed_scheduled_young_and_fully_paid():
    rec = [inv("I4", "D3", 200, 900_000, status="محل نزاع"), inv("I5", "D4", 200, 900_000, status="مجدول"),
           inv("I6", "D5", 30, 900_000, status="عادي"), inv("I7", "D6", 200, 900_000, paid=900_000)]
    opps, ex = detect_opportunities(make_data(receivables=rec))
    assert opps.empty or not opps["opp_type"].eq("collection").any()
    txt = " ".join(ex["السبب"])
    assert "نزاع" in txt and "مجدولة" in txt and "أقل من 90" in txt


def test_collection_small_debtors_are_pooled():
    rec = [inv(f"P{i}", f"S{i}", 150, 20_000) for i in range(5)]
    opps, _ = detect_opportunities(make_data(receivables=rec))
    assert list(opps["opp_id"]) == ["COL-POOL"]


def test_changing_recovery_rate_changes_result():
    rec = [inv("I8", "D7", 120, 1_000_000)]
    data = make_data(receivables=rec)
    a = detect_opportunities(data)[0].iloc[0]["in_year"]
    b = detect_opportunities(data, {"recovery_rates": {"90-180": 0.8, "181-365": 0.35, "365+": 0.2}})[0].iloc[0]["in_year"]
    assert b > a and math.isclose(b / a, 0.8 / 0.5, rel_tol=1e-9)


def test_no_opportunities_dataset():
    opps, ex = detect_opportunities(make_data())
    assert opps.empty
    assert {"annual_potential", "in_year", "priority_score"} <= set(opps.columns)


def test_synthetic_engine_outputs_are_evidence_backed(rev):
    opps, ex = detect_opportunities(rev)
    assert len(opps) > 10 and len(ex) > 5
    for o in opps.itertuples():
        assert o.evidence and o.method and o.assumptions and o.approvals
        assert o.in_year >= 0 and o.annual_potential >= 0
    assert opps["opp_id"].is_unique
    # الترتيب تنازلي حسب الأولوية
    assert list(opps["priority_score"]) == sorted(opps["priority_score"], reverse=True)
