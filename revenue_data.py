"""تحميل بيانات الإيرادات والتحقق منها كمجموعة واحدة (لا استبدال جزئي)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import pandas as pd

from .config import DATA_DIR, demo_mode
from .schemas import REVENUE_TABLES, SETTINGS_KEYS
from .validation import ValidationReport, check_fks, check_labels, read_any, validate_table


OPTIONAL_EMPTY = {"assets", "contracts", "receivables", "market_benchmarks"}


@dataclass(frozen=True)
class RevenueSettings:
    fiscal_year: int
    annual_target_sar: float
    snapshot_date: date
    financial_basis: str  # cash | accrual
    data_label: str
    source_note: str

    @property
    def year_end(self) -> date:
        return date(self.fiscal_year, 12, 31)

    @property
    def year_start(self) -> date:
        return date(self.fiscal_year, 1, 1)

    @property
    def days_in_year(self) -> int:
        return (self.year_end - self.year_start).days + 1

    @property
    def remaining_days(self) -> int:
        """الأيام المتبقية بعد تاريخ اللقطة حتى 31 ديسمبر (شاملة)."""
        return max(0, (self.year_end - self.snapshot_date).days)

    @property
    def basis_label(self) -> str:
        return "نقدي (الإيراد = المبالغ المحصلة فعليًا)" if self.financial_basis == "cash" else "استحقاق (الإيراد عند نشوء الحق)"


@dataclass(frozen=True)
class RevenueData:
    settings: RevenueSettings
    sources: pd.DataFrame
    assets: pd.DataFrame
    contracts: pd.DataFrame
    receivables: pd.DataFrame
    benchmarks: pd.DataFrame

    def with_settings(self, **kw) -> "RevenueData":
        return replace(self, settings=replace(self.settings, **kw))

    def tables(self) -> dict:
        return {
            "settings": settings_to_frame(self.settings),
            "revenue_sources": self.sources,
            "assets": self.assets,
            "contracts": self.contracts,
            "receivables": self.receivables,
            "market_benchmarks": self.benchmarks,
        }


def settings_to_frame(s: RevenueSettings) -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("fiscal_year", str(s.fiscal_year)),
            ("annual_target_sar", f"{s.annual_target_sar:.2f}"),
            ("snapshot_date", s.snapshot_date.isoformat()),
            ("financial_basis", s.financial_basis),
            ("data_label", s.data_label),
            ("source_note", s.source_note),
        ],
        columns=["key", "value"],
    )


def _parse_settings(df: pd.DataFrame, rep: ValidationReport) -> RevenueSettings | None:
    title = REVENUE_TABLES["settings"].title
    kv = {str(k).strip(): (None if v is None else str(v).strip()) for k, v in zip(df["key"], df["value"])}
    missing = [k for k in SETTINGS_KEYS if not kv.get(k)]
    if missing:
        rep.err(title, "إعدادات مفقودة: " + "، ".join(missing))
        return None
    ok = True
    try:
        fy = int(float(kv["fiscal_year"]))
        if not 2000 <= fy <= 2100:
            raise ValueError
    except ValueError:
        rep.err(title, "السنة المالية غير صالحة")
        ok = False
        fy = None
    try:
        target = float(kv["annual_target_sar"])
        if target < 0 or target != target or target in (float("inf"),):
            raise ValueError
    except ValueError:
        rep.err(title, "المستهدف السنوي يجب أن يكون رقمًا غير سالب ومحدودًا")
        ok = False
        target = None
    try:
        snap = pd.to_datetime(kv["snapshot_date"], format="ISO8601").date()
    except (ValueError, TypeError):
        rep.err(title, "تاريخ اللقطة غير صالح (YYYY-MM-DD)")
        ok = False
        snap = None
    basis = kv["financial_basis"].lower()
    if basis not in ("cash", "accrual"):
        rep.err(title, "الأساس المالي يجب أن يكون cash أو accrual")
        ok = False
    label = kv["data_label"]
    if label not in ("synthetic", "real"):
        rep.err(title, "data_label يجب أن يكون synthetic أو real")
        ok = False
    if ok and fy and snap and snap.year != fy:
        rep.err(title, f"تاريخ اللقطة {snap.isoformat()} خارج السنة المالية {fy}")
        ok = False
    if not ok:
        return None
    return RevenueSettings(fy, target, snap, basis, label, kv["source_note"])


def validate_revenue_bundle(raw: dict, demo: bool | None = None) -> tuple[RevenueData | None, ValidationReport]:
    """يتحقق من مجموعة جداول الإيرادات كاملة. يعيد None عند أي خطأ (لا استبدال جزئي)."""
    demo = demo_mode() if demo is None else demo
    rep = ValidationReport()
    clean = {}
    for key, spec in REVENUE_TABLES.items():
        # الأصول والعقود والمستحقات والمراجع قد تكون فارغة فعلًا (لا فرص)، لكن أعمدتها مطلوبة
        df, r = validate_table(raw.get(key), spec, allow_empty=key in OPTIONAL_EMPTY)
        rep.extend(r)
        clean[key] = df
    if not rep.ok:
        return None, rep
    settings = _parse_settings(clean["settings"], rep)
    if settings is None:
        return None, rep
    check_fks(clean, REVENUE_TABLES, rep)
    check_labels({k: v for k, v in clean.items() if k != "settings"}, REVENUE_TABLES, rep, demo, {settings.data_label})

    # قيود منطقية بين الأعمدة
    c = clean["contracts"]
    bad = c["end_date"] < c["start_date"]
    if bad.any():
        rep.err("العقود الاستثمارية", "تاريخ النهاية قبل تاريخ البداية للعقود: " + "، ".join(c.loc[bad, "contract_id"].astype(str)[:6]))
    r = clean["receivables"]
    bad = r["due_date"] < r["invoice_date"]
    if bad.any():
        rep.err("المستحقات والتحصيل", "تاريخ الاستحقاق قبل تاريخ الفاتورة: " + "، ".join(r.loc[bad, "invoice_id"].astype(str)[:6]))
    bad = r["amount_paid_sar"] > r["amount_due_sar"] + 0.005
    if bad.any():
        rep.err("المستحقات والتحصيل", "المسدد أكبر من المستحق في الفواتير: " + "، ".join(r.loc[bad, "invoice_id"].astype(str)[:6]))
    outstanding = r["amount_due_sar"] - r["amount_paid_sar"]
    bad = r["expected_baseline_collection_sar"] > outstanding + 0.005
    if bad.any():
        rep.err("المستحقات والتحصيل", "التحصيل المتوقع أصلًا أكبر من الرصيد غير المحصل في الفواتير: " + "، ".join(r.loc[bad, "invoice_id"].astype(str)[:6]))
    bad = r["invoice_date"].dt.date > settings.snapshot_date
    if bad.any():
        rep.err("المستحقات والتحصيل", "فواتير بتاريخ لاحق لتاريخ اللقطة: " + "، ".join(r.loc[bad, "invoice_id"].astype(str)[:6]))
    b = clean["market_benchmarks"]
    bad = b["upper_annual_rate_sar"] < b["ref_annual_rate_sar"]
    if bad.any():
        rep.err("المراجع السوقية", "الحد الأعلى أقل من المعدل المرجعي في: " + "، ".join(b.loc[bad, "benchmark_id"].astype(str)[:6]))
    dupkey = b.duplicated(subset=["category", "location_tier"], keep=False)
    if dupkey.any():
        rep.err("المراجع السوقية", "أكثر من مرجع لنفس الفئة وفئة الموقع")
    a = clean["assets"]
    bad = a["restricted"].astype(bool) & a["restriction_reason"].isna()
    if bad.any():
        rep.warn("الأصول والأراضي", "أصول مقيدة دون ذكر سبب القيد: " + "، ".join(a.loc[bad, "asset_id"].astype(str)[:6]))

    s = clean["revenue_sources"]
    tsum = float(s["annual_target_sar"].sum())
    if settings.annual_target_sar > 0 and abs(tsum - settings.annual_target_sar) / settings.annual_target_sar > 0.005:
        rep.warn("مصادر الإيرادات", f"مجموع مستهدفات المصادر ({tsum:,.0f}) لا يطابق المستهدف السنوي في الإعدادات ({settings.annual_target_sar:,.0f}). يُعتمد مستهدف الإعدادات في حساب الفجوة.")

    if not rep.ok:
        return None, rep
    data = RevenueData(
        settings=settings,
        sources=clean["revenue_sources"],
        assets=clean["assets"],
        contracts=clean["contracts"],
        receivables=clean["receivables"],
        benchmarks=clean["market_benchmarks"],
    )
    return data, rep


def read_revenue_files(files) -> dict:
    """يقبل ملف Excel واحدًا بأوراق متعددة أو عدة ملفات CSV مسماة بأسماء الجداول."""
    raw = {}
    for f in files:
        for k, v in read_any(f).items():
            raw[k] = v
    return raw


def load_synthetic_revenue(data_dir: Path = DATA_DIR) -> RevenueData:
    raw = {}
    for key in REVENUE_TABLES:
        raw[key] = pd.read_csv(Path(data_dir) / f"{key}.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    data, rep = validate_revenue_bundle(raw, demo=True)
    if data is None:
        raise RuntimeError("البيانات التجريبية غير صالحة: " + " | ".join(rep.errors))
    return data
