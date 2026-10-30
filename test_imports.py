"""الاستيراد: قبول الصحيح ورفض الخاطئ دون فقد البيانات الحالية، لكل من الإيرادات والأداء."""
from __future__ import annotations

import io

import pandas as pd
import pytest

from core.exports import perf_backup_excel
from core.performance import merge_records_upload, read_perf_files, validate_perf_bundle
from core.revenue_data import validate_revenue_bundle
from tests.conftest import make_raw


def errs(raw, demo=True):
    data, rep = validate_revenue_bundle(raw, demo=demo)
    return data, " | ".join(rep.errors)


SHOP = ("S1", "محلات", "محل تجاري", "x", "A", "تجاري", 1000, 30, True, True, "مستغل جزئيًا", 0.2, 200_000, False, "")


def test_valid_bundle_accepted():
    data, e = errs(make_raw(assets=[SHOP]))
    assert data is not None and e == ""


def test_missing_required_column_rejected():
    raw = make_raw()
    raw["assets"] = raw["assets"].drop(columns=["area_sqm"])
    data, e = errs(raw)
    assert data is None and "area_sqm" in e and "مفقودة" in e


def test_duplicate_ids_rejected():
    data, e = errs(make_raw(assets=[SHOP, SHOP]))
    assert data is None and "مكررة" in e


def test_broken_reference_rejected():
    raw = make_raw(contracts=[("C1", "NOPE", "SRC01", "I", "x", "2021-01-01", "2026-11-30", 100, 50000, True, None, False, "ساري")])
    data, e = errs(raw)
    assert data is None and "NOPE" in e and "مراجع غير موجودة" in e


def test_bad_dates_rejected():
    raw = make_raw(contracts=[("C1", "A0", "SRC01", "I", "x", "2021-13-45", "2026-11-30", 100, 50000, True, None, False, "ساري")])
    assert errs(raw)[0] is None and "تواريخ غير صالحة" in errs(raw)[1]
    raw = make_raw(contracts=[("C1", "A0", "SRC01", "I", "x", "2027-01-01", "2026-11-30", 100, 50000, True, None, False, "ساري")])
    assert "قبل تاريخ البداية" in errs(raw)[1]
    raw = make_raw(snapshot="2026-09-31")
    assert "تاريخ اللقطة غير صالح" in errs(raw)[1]


def test_negative_and_infinite_values_rejected():
    bad = list(SHOP)
    bad[6] = -5
    assert "سالبة" in errs(make_raw(assets=[tuple(bad)]))[1] or "الحد الأدنى" in errs(make_raw(assets=[tuple(bad)]))[1]
    bad[6] = "inf"
    assert "غير محدودة" in errs(make_raw(assets=[tuple(bad)]))[1]
    raw = make_raw()
    raw["revenue_sources"].loc[0, "realized_to_date_sar"] = "-1"
    assert "سالبة" in errs(raw)[1]


def test_ratio_out_of_bounds_rejected():
    bad = list(SHOP)
    bad[11] = 1.5
    assert "خارج الحدود" in errs(make_raw(assets=[tuple(bad)]))[1]


def test_paid_more_than_due_rejected():
    rec = [("I1", "D1", "منشأة", "", "SRC01", "2026-01-01", "2026-02-01", 100, 150, "متأخر", 0)]
    assert "المسدد أكبر من المستحق" in errs(make_raw(receivables=rec))[1]


def test_mixed_real_and_synthetic_rejected():
    raw = make_raw(assets=[SHOP])
    raw["assets"].loc[0, "data_label"] = "real"
    data, e = errs(raw, demo=False)
    assert data is None and "خلط" in e


def test_demo_mode_rejects_real_data():
    data, e = errs(make_raw(assets=[SHOP], label="real"), demo=True)
    assert data is None and "التجريبية" in e
    data, e = errs(make_raw(assets=[SHOP], label="real"), demo=False)
    assert data is not None


def test_revenue_excel_roundtrip(rev):
    from core.exports import _Book
    b = _Book()
    for k, df in rev.tables().items():
        b.table(df, k)
    from core.revenue_data import read_revenue_files
    f = io.BytesIO(b.bytes())
    f.name = "data.xlsx"
    data, rep = validate_revenue_bundle(read_revenue_files([f]), demo=True)
    assert data is not None, rep.errors
    assert data.sources["realized_to_date_sar"].sum() == rev.sources["realized_to_date_sar"].sum()
    assert len(data.receivables) == len(rev.receivables)


# ------------------------------------------------------------------ الأداء
def recs(rows):
    return pd.DataFrame(rows, columns=["dept_id", "month", "kpi_id", "target", "actual", "data_label"]).astype(str).replace({"None": ""})


def test_perf_merge_valid_upload_replaces_only_uploaded_dept_months(perf):
    up = recs([("D01", "2026-09", k, 90, 50, "synthetic") for k in ("PLAN", "TIME", "QUALITY")] + [("D02", "2026-10", "PLAN", 90, 80, "synthetic")])
    new, rep, info = merge_records_upload(perf, {"performance_records": up}, demo=True)
    assert rep.ok, rep.errors
    assert info["replaced_rows"] == 3 and info["dept_months"] == 2
    d01 = new.records[(new.records["dept_id"] == "D01") & (new.records["month"] == "2026-09")]
    assert (d01["actual"] == 50).all()
    other = new.records[(new.records["dept_id"] == "D03") & (new.records["month"] == "2026-09")]
    assert len(other) == 3
    # البيانات الأصلية لم تتغير (لا تعديل في المكان)
    assert (perf.records[(perf.records["dept_id"] == "D01") & (perf.records["month"] == "2026-09")]["actual"] != 50).all()


@pytest.mark.parametrize("rows,msg", [
    ([("D01", "2026-09", "PLAN", 90, 50, "synthetic"), ("D01", "2026-09", "PLAN", 90, 60, "synthetic")], "مكررة"),
    ([("D01", "2026-09", "PLAN", 90, 150, "synthetic")], "خارج الحدود"),
    ([("D01", "2026-09", "PLAN", 0, 50, "synthetic")], "الحد الأدنى"),
    ([("D99", "2026-09", "PLAN", 90, 50, "synthetic")], "مراجع غير موجودة"),
    ([("D01", "2026/09", "PLAN", 90, 50, "synthetic")], "صيغة شهر"),
    ([("D01", "2026-09", "XYZ", 90, 50, "synthetic")], "مراجع غير موجودة"),
    ([("D01", "2026-09", "PLAN", 90, -1, "synthetic")], "سالبة"),
    ([("D01", "2026-09", "PLAN", 90, 50, "real")], "خلط"),
])
def test_perf_invalid_uploads_rejected_without_changes(perf, rows, msg):
    before = perf.records.copy()
    new, rep, _ = merge_records_upload(perf, {"performance_records": recs(rows)}, demo=False)
    assert new is None and not rep.ok
    assert msg in " | ".join(rep.errors)
    pd.testing.assert_frame_equal(perf.records, before)


def test_perf_missing_actual_allowed_and_kept_blank(perf):
    new, rep, _ = merge_records_upload(perf, {"performance_records": recs([("D01", "2026-10", "PLAN", 90, None, "synthetic")])}, demo=True)
    assert rep.ok
    r = new.records[(new.records["dept_id"] == "D01") & (new.records["month"] == "2026-10")].iloc[0]
    assert pd.isna(r["actual"])


def test_perf_csv_single_file_and_missing_columns(perf):
    f = io.BytesIO("dept_id,month,kpi_id,target\nD01,2026-10,PLAN,90\n".encode("utf-8-sig"))
    f.name = "results.csv"
    new, rep, _ = merge_records_upload(perf, read_perf_files([f]), demo=True)
    assert new is None and "actual" in " | ".join(rep.errors)


def test_perf_backup_roundtrip(perf):
    f = io.BytesIO(perf_backup_excel(perf))
    f.name = "backup.xlsx"
    new, rep = validate_perf_bundle(read_perf_files([f]), demo=True)
    assert new is not None, rep.errors
    assert len(new.records) == len(perf.records)
    assert new.records["actual"].isna().sum() == perf.records["actual"].isna().sum()


def test_sqlite_local_persistence_roundtrip(perf, tmp_path):
    from core.performance import load_sqlite, save_sqlite
    db = tmp_path / "perf.db"
    assert load_sqlite(db) is None
    save_sqlite(perf, db)
    back = load_sqlite(db)
    assert back is not None
    assert len(back.records) == len(perf.records)
    assert back.records["actual"].isna().sum() == perf.records["actual"].isna().sum()
    assert set(back.depts["dept_id"]) == set(perf.depts["dept_id"])
