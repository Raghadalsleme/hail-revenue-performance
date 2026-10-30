"""تصنيف الأقسام وحدود 70 و90، الأوزان وسقف التحقيق، المفقود مقابل الصفر، مقارنة الأشهر وتصفية الإدارة."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from core.performance import (PerfSettings, add_dept, classify, default_settings, gd_kpis, kpi_achievement, month_summary, prev_month,
                              rename_gd, trend, update_depts, upsert_month)

S = PerfSettings(weights={"PLAN": 50, "TIME": 30, "QUALITY": 20})


def with_records(perf, rows):
    df = pd.DataFrame(rows, columns=["dept_id", "month", "kpi_id", "target", "actual"])
    df["data_label"] = "synthetic"
    df[["target", "actual"]] = df[["target", "actual"]].astype(float)
    return replace(perf, records=df)


def test_kpi_achievement_rules():
    assert kpi_achievement(90, 45) == pytest.approx(50)
    assert kpi_achievement(90, 120) == 100  # سقف 100%
    assert kpi_achievement(90, 0) == 0  # صفر فعلي
    assert kpi_achievement(90, None) is None and kpi_achievement(None, 50) is None
    assert kpi_achievement(90, np.nan) is None
    assert kpi_achievement(0, 50) is None  # مستهدف صفري غير صالح


@pytest.mark.parametrize("score,status", [(90.0, "good"), (89.99, "medium"), (70.0, "medium"), (69.99, "intervene"), (100, "good"), (0, "intervene"), (None, "incomplete")])
def test_classification_boundaries(score, status):
    assert classify(score, S) == status


def test_weighted_score_and_cap_prevents_compensation(perf):
    p = with_records(perf, [("D01", "2026-09", "PLAN", 90, 180), ("D01", "2026-09", "TIME", 85, 42.5), ("D01", "2026-09", "QUALITY", 95, 47.5)])
    r = month_summary(p, "GD-A", "2026-09", S).set_index("dept_id").loc["D01"]
    # 0.5×100 (لا 200) + 0.3×50 + 0.2×50 = 75
    assert r["score"] == pytest.approx(75.0)
    assert r["status"] == "medium"


def test_float_artifacts_rounded_before_classification(perf):
    # كل المؤشرات 90% تحقيق => 90 بالضبط => جيد
    p = with_records(perf, [("D01", "2026-09", k, 100, 90) for k in ("PLAN", "TIME", "QUALITY")])
    r = month_summary(p, "GD-A", "2026-09", S).set_index("dept_id").loc["D01"]
    assert r["score"] == 90.0 and r["status"] == "good"


def test_missing_value_is_not_zero(perf):
    base = [("D01", "2026-09", "PLAN", 90, 90), ("D01", "2026-09", "TIME", 85, 85)]
    missing = month_summary(with_records(perf, base + [("D01", "2026-09", "QUALITY", 95, None)]), "GD-A", "2026-09", S).set_index("dept_id").loc["D01"]
    zero = month_summary(with_records(perf, base + [("D01", "2026-09", "QUALITY", 95, 0)]), "GD-A", "2026-09", S).set_index("dept_id").loc["D01"]
    assert missing["status"] == "incomplete" and (missing["score"] is None or np.isnan(missing["score"]))
    assert "جودة المخرجات" in missing["reason"]
    assert zero["status"] == "medium" and zero["score"] == pytest.approx(80.0)
    assert "صفري" in zero["reason"]


def test_department_without_any_data_is_grey_not_red(perf):
    p = with_records(perf, [("D01", "2026-09", k, 90, 90) for k in ("PLAN", "TIME", "QUALITY")])
    sm = month_summary(p, "GD-A", "2026-09", S).set_index("dept_id")
    assert sm.loc["D02", "status"] == "incomplete"
    assert "لا توجد بيانات" in sm.loc["D02", "reason"]
    k = gd_kpis(sm.reset_index())
    assert k["n_intervene"] == 0 and k["n_complete"] == 1 and k["avg_score"] == pytest.approx(100.0)


def test_weights_change_score(perf):
    p = with_records(perf, [("D01", "2026-09", "PLAN", 100, 100), ("D01", "2026-09", "TIME", 100, 50), ("D01", "2026-09", "QUALITY", 100, 50)])
    a = month_summary(p, "GD-A", "2026-09", S).set_index("dept_id").loc["D01", "score"]
    b = month_summary(p, "GD-A", "2026-09", PerfSettings(weights={"PLAN": 20, "TIME": 40, "QUALITY": 40})).set_index("dept_id").loc["D01", "score"]
    assert a == pytest.approx(75.0) and b == pytest.approx(60.0)


def test_settings_validation():
    assert PerfSettings(weights={"PLAN": 50, "TIME": 30, "QUALITY": 10}).validate()
    assert PerfSettings(weights={"PLAN": 50, "TIME": 30, "QUALITY": 20}, green=70, yellow=80).validate()
    assert not S.validate()


def test_custom_thresholds_change_status(perf):
    p = with_records(perf, [("D01", "2026-09", k, 100, 85) for k in ("PLAN", "TIME", "QUALITY")])
    assert month_summary(p, "GD-A", "2026-09", S).set_index("dept_id").loc["D01", "status"] == "medium"
    assert month_summary(p, "GD-A", "2026-09", replace(S, green=85)).set_index("dept_id").loc["D01", "status"] == "good"


def test_previous_calendar_month_comparison(perf):
    assert prev_month("2026-01") == "2025-12" and prev_month("2026-09") == "2026-08"
    sm = month_summary(perf, "GD-A", "2026-05", default_settings(perf)).set_index("dept_id")
    # D05 لا يملك بيانات أبريل => لا مقارنة
    assert sm.loc["D05", "delta"] is None or np.isnan(sm.loc["D05", "delta"])
    assert "أبريل" in sm.loc["D05", "compare_note"]
    assert not np.isnan(sm.loc["D01", "delta"])
    assert sm.loc["D01", "delta"] == pytest.approx(sm.loc["D01", "score"] - sm.loc["D01", "prev_score"], abs=0.011)


def test_incomplete_previous_month_gives_no_comparison(perf):
    s = default_settings(perf)
    sm = month_summary(perf, "GD-A", "2026-09", s).set_index("dept_id")
    assert sm.loc["D03", "status"] == "incomplete"
    p = with_records(perf, [r for r in perf.records[["dept_id", "month", "kpi_id", "target", "actual"]].itertuples(index=False)] +
                     [("D03", "2026-10", k, 90, 90) for k in ("PLAN", "TIME", "QUALITY")])
    r = month_summary(p, "GD-A", "2026-10", s).set_index("dept_id").loc["D03"]
    assert r["status"] == "good" and (r["delta"] is None or np.isnan(r["delta"]))
    assert "غير مكتملة" in r["compare_note"]


def test_general_department_filter(perf):
    s = default_settings(perf)
    a = month_summary(perf, "GD-A", "2026-09", s)
    b = month_summary(perf, "GD-B", "2026-09", s)
    assert set(a["dept_id"]) == {f"D0{i}" for i in range(1, 7)}
    assert set(b["dept_id"]) == {"D07", "D08", "D09", "D10"}


def test_trend_keeps_missing_month_as_gap(perf):
    t = trend(perf, "GD-A", default_settings(perf))
    row = t[(t["dept_id"] == "D05") & (t["month"] == "2026-04")].iloc[0]
    assert row["no_data"] and (row["score"] is None or np.isnan(row["score"]))
    assert len(t["month"].unique()) == 9


def test_rename_keeps_history_and_ids(perf):
    s = default_settings(perf)
    before = month_summary(perf, "GD-A", "2026-08", s).set_index("dept_id").loc["D02", "score"]
    edits = perf.depts[perf.depts["gd_id"] == "GD-A"][["dept_id", "dept_name", "sort_order", "active"]].copy()
    edits.loc[edits["dept_id"] == "D02", "dept_name"] = "اسم جديد للقسم"
    p2 = rename_gd(update_depts(perf, edits), "GD-A", "إدارة عامة باسم جديد")
    r = month_summary(p2, "GD-A", "2026-08", s).set_index("dept_id").loc["D02"]
    assert r["dept_name"] == "اسم جديد للقسم" and r["score"] == before
    assert p2.gds.set_index("gd_id").at["GD-A", "gd_name"] == "إدارة عامة باسم جديد"


def test_add_department_gets_new_stable_id(perf):
    p2, did = add_dept(perf, "GD-A", "قسم إضافي")
    assert did == "D11" and did not in set(perf.depts["dept_id"])
    sm = month_summary(p2, "GD-A", "2026-09", default_settings(p2)).set_index("dept_id")
    assert sm.loc[did, "status"] == "incomplete"


def test_upsert_month_blank_is_not_zero_and_only_month_replaced(perf):
    from core.performance import month_wide
    w = month_wide(perf, "GD-A", "2026-10")
    w.loc[w["dept_id"] == "D01", ["PLAN_target", "PLAN_actual", "TIME_target", "TIME_actual", "QUALITY_target"]] = [90, 90, 85, 85, 95]
    p2, errs = upsert_month(perf, "2026-10", w.drop(columns=["dept_name"]))
    assert not errs
    oct_rows = p2.records[p2.records["month"] == "2026-10"]
    q = oct_rows[(oct_rows["dept_id"] == "D01") & (oct_rows["kpi_id"] == "QUALITY")].iloc[0]
    assert np.isnan(q["actual"])  # فارغ وليس صفرًا
    assert len(p2.records[p2.records["month"] != "2026-10"]) == len(perf.records)
    bad = w.copy()
    bad.loc[bad["dept_id"] == "D02", "PLAN_target"] = 0
    _, errs = upsert_month(perf, "2026-10", bad.drop(columns=["dept_name"]))
    assert errs and "أكبر من صفر" in errs[0]
