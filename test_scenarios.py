"""السيناريوهات: منع التكرار والتعارض، السقوف، الأساس المالي، الاختيار التلقائي، وتغير النتائج بتغير المدخلات."""
from __future__ import annotations

import pytest

from core.opportunities import detect_opportunities, estimate
from core.revenue import auto_select, compute_kpis, resolve_selection, scenario_result
from tests.conftest import make_data
from tests.test_revenue import SHOP, inv

LAND = ("L9", "أرض واجهة", "أرض فضاء", "x", "A", "تجاري", 3000, 100, True, True, "غير مستغل", 0, 0, False, "")


def _setup(**kw):
    data = make_data(assets=[SHOP, LAND], receivables=[inv("I1", "D1", 120, 2_000_000, baseline=100_000)], **kw)
    opps, _ = detect_opportunities(data)
    return data, opps, compute_kpis(data)


def test_duplicate_ids_counted_once():
    data, opps, k = _setup()
    once = scenario_result(opps, ["COL-D1"], 1.0, k, "cash")
    twice = scenario_result(opps, ["COL-D1", "COL-D1"], 1.0, k, "cash")
    assert once["contribution"] == twice["contribution"]
    assert twice["selection"].kept == ["COL-D1"]


def test_conflicting_alternatives_on_same_asset_not_summed():
    data, opps, k = _setup()
    alts = list(opps.loc[opps["ref_ids"] == "L9", "opp_id"])
    assert len(alts) == 2
    res = scenario_result(opps, alts, 1.0, k, "cash")
    assert len(res["selection"].kept) == 1 and len(res["selection"].dropped) == 1
    kept = res["selection"].kept[0]
    assert res["recurring_in_year"] == pytest.approx(estimate(opps.set_index("opp_id").loc[kept], 1.0)["in_year"])
    assert res["recurring_in_year"] < sum(estimate(opps.set_index("opp_id").loc[i], 1.0)["in_year"] for i in alts) + 1e-9


def test_unknown_ids_ignored_with_reason():
    data, opps, k = _setup()
    sel = resolve_selection(opps, ["NOPE"])
    assert sel.kept == [] and sel.dropped[0][0] == "NOPE"


def test_scenarios_ordered_and_lease_capped_at_full_occupancy():
    data, opps, k = _setup()
    ids = ["LSE-S1-1", "COL-D1"]
    c, b, o = (scenario_result(opps, ids, m, k, "cash")["contribution"] for m in (0.7, 1.0, 1.2))
    assert c < b < o
    lease = opps.set_index("opp_id").loc["LSE-S1-1"]
    e = estimate(lease, 1.2)
    assert e["capped"]  # 0.9 × 1.2 = 1.08 > 1
    assert e["annual"] == pytest.approx(1000 * 1000 * 1.0 - 200_000)


def test_accrual_basis_excludes_collection_from_gap():
    data, opps, k = _setup(basis="accrual")
    r = scenario_result(opps, ["COL-D1"], 1.0, k, "accrual")
    assert r["one_time_in_year"] > 0
    assert r["contribution"] == 0
    assert r["excluded_cash_only"] == pytest.approx(r["one_time_in_year"])
    assert auto_select(opps, k, 1.0, "accrual") == [i for i in auto_select(opps, k, 1.0, "accrual") if not i.startswith("COL")]


def test_remaining_gap_and_surplus():
    data, opps, k = _setup()
    r = scenario_result(opps, ["COL-D1"], 1.0, k, "cash")
    # الفجوة المتوقعة 20 مليون (لا إيراد أساسي) والفرص أقل منها بكثير
    assert r["remaining_gap"] == pytest.approx(k["projected_gap"] - r["contribution"])
    assert r["surplus"] == 0
    data2, opps2, k2 = (lambda d: (d, detect_opportunities(d)[0], compute_kpis(d)))(
        make_data(target=80_500_000, realized=80_000_000, receivables=[inv("I1", "D1", 120, 2_000_000)]))
    r2 = scenario_result(opps2, ["COL-D1"], 1.0, k2, "cash")
    assert r2["remaining_gap"] == 0 and r2["surplus"] == pytest.approx(k2["realized"] + r2["contribution"] - k2["target"])


def test_auto_select_stops_when_gap_covered_and_skips_conflicts():
    data = make_data(target=80_300_000, realized=80_000_000, assets=[SHOP, LAND], receivables=[inv("I1", "D1", 120, 2_000_000)])
    opps, _ = detect_opportunities(data)
    k = compute_kpis(data)
    sel = auto_select(opps, k, 1.0, "cash")
    assert sel == ["COL-D1"]  # تكفي وحدها لتغطية 300 ألف
    groups = opps.set_index("opp_id").loc[auto_select(opps, compute_kpis(make_data(assets=[SHOP, LAND])), 1.0, "cash"), "conflict_group"]
    assert groups.is_unique


def test_no_opportunities_shows_full_gap():
    data = make_data()
    opps, _ = detect_opportunities(data)
    k = compute_kpis(data)
    r = scenario_result(opps, [], 1.0, k, "cash")
    assert r["contribution"] == 0 and r["remaining_gap"] == k["projected_gap"] == 20_000_000
    assert auto_select(opps, k, 1.0, "cash") == []


def test_changing_target_changes_gap_and_result():
    a = compute_kpis(make_data(target=100_000_000))
    b = compute_kpis(make_data(target=90_000_000))
    assert a["gap_to_date"] - b["gap_to_date"] == 10_000_000


def test_synthetic_default_scenario_does_not_cover_gap(rev):
    opps, _ = detect_opportunities(rev)
    k = compute_kpis(rev)
    for m in (0.7, 1.0, 1.2):
        r = scenario_result(opps, auto_select(opps, k, m, "cash"), m, k, "cash")
        assert r["remaining_gap"] > 0  # البيانات التجريبية مصممة بحيث لا تكفي الفرص
        assert r["contribution"] + r["remaining_gap"] == pytest.approx(k["projected_gap"])
