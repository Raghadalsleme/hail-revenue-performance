"""أدوات مشتركة للاختبارات: بناء مجموعات بيانات صغيرة محسوبة يدويًا."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.performance import load_synthetic_perf  # noqa: E402
from core.revenue_data import load_synthetic_revenue, validate_revenue_bundle  # noqa: E402

L = "synthetic"


@pytest.fixture(scope="session")
def rev():
    return load_synthetic_revenue()


@pytest.fixture(scope="session")
def perf():
    return load_synthetic_perf()


def bench_rows():
    return [
        ("BM-1", "أرض تجارية", "A", "م²", 100, 120, 0.9, "2026-06-30", "test"),
        ("BM-2", "محل تجاري", "A", "م²", 1000, 1200, 0.9, "2026-06-30", "test"),
        ("BM-3", "لوحة إعلانية", "A", "لوحة", 100000, 120000, 0.8, "2026-06-30", "test"),
        ("BM-4", "مكاتب", "A", "م²", 500, 600, 0.8, "2026-06-30", "test"),
    ]


ASSET_COLS = ["asset_id", "asset_name", "asset_type", "district", "location_tier", "zoning", "area_sqm", "frontage_m", "on_main_road",
              "utilities_available", "status", "current_occupancy", "current_annual_revenue_sar", "restricted", "restriction_reason"]
CONTRACT_COLS = ["contract_id", "asset_id", "source_id", "investor_ref", "activity", "start_date", "end_date", "leased_area_sqm",
                 "annual_value_sar", "renegotiable", "max_renewal_increase_pct", "in_dispute", "status"]
RECV_COLS = ["invoice_id", "debtor_id", "debtor_type", "contract_id", "source_id", "invoice_date", "due_date", "amount_due_sar",
             "amount_paid_sar", "status", "expected_baseline_collection_sar"]


def make_raw(target=100_000_000, realized=80_000_000, baseline=0, snapshot="2026-09-30", basis="cash",
             assets=None, contracts=None, receivables=None, benchmarks=None, label=L):
    """يبني قاموس جداول خام (نصوص) كما لو قُرئت من ملفات."""
    def df(rows, cols):
        d = pd.DataFrame(rows, columns=cols)
        d["data_label"] = label
        return d.astype(str).replace({"None": "", "nan": ""})
    settings = pd.DataFrame([("fiscal_year", snapshot[:4]), ("annual_target_sar", str(target)), ("snapshot_date", snapshot),
                             ("financial_basis", basis), ("data_label", label), ("source_note", "test")], columns=["key", "value"])
    sources = df([("SRC01", "مصدر", "رسوم", target, realized, baseline)], ["source_id", "source_name", "category", "annual_target_sar", "realized_to_date_sar", "expected_remaining_sar"])
    default_asset = [("A0", "أصل مؤجر", "محل تجاري", "x", "A", "تجاري", 100, 10, True, True, "مستغل", 1.0, 100000, False, "")]
    return {
        "settings": settings,
        "revenue_sources": sources,
        "assets": df((assets or []) + default_asset, ASSET_COLS),
        "contracts": df(contracts or [], CONTRACT_COLS),
        "receivables": df(receivables or [], RECV_COLS),
        "market_benchmarks": df(benchmarks or bench_rows(), ["benchmark_id", "category", "location_tier", "unit", "ref_annual_rate_sar", "upper_annual_rate_sar", "expected_occupancy", "as_of_date", "source_note"]),
    }


def make_data(**kw):
    data, rep = validate_revenue_bundle(make_raw(**kw), demo=True)
    assert data is not None, rep.errors
    return data


def days(a: str, b: str) -> int:
    """عدد الأيام من a إلى b شاملًا."""
    return (date.fromisoformat(b) - date.fromisoformat(a)).days + 1
