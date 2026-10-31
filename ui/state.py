"""حالة الجلسة: بيانات الإيرادات وبيانات الأداء منفصلتان تمامًا (رفع إحداهما لا يمس الأخرى)."""
from __future__ import annotations

import streamlit as st

from core.config import ENGINE_DEFAULTS, PRIORITY_WEIGHTS_DEFAULT, SCENARIOS_DEFAULT, local_db_path
from core.opportunities import detect_opportunities, score_priority
from core.performance import PerfData, default_settings, load_sqlite, load_synthetic_perf, save_sqlite
from core.revenue import auto_select, compute_kpis
from core.revenue_data import RevenueData, load_synthetic_revenue

ss = st.session_state


@st.cache_resource(show_spinner=False)
def _synthetic_revenue() -> RevenueData:
    return load_synthetic_revenue()


@st.cache_resource(show_spinner=False)
def _synthetic_perf() -> PerfData:
    return load_synthetic_perf()


def init():
    if "rev_data" not in ss:
        reset_revenue()
    if "perf" not in ss:
        db = local_db_path()
        perf = load_sqlite(db) if db else None
        ss.perf_source = "sqlite" if perf is not None else "synthetic"
        ss.perf = perf if perf is not None else _synthetic_perf()
        ss.perf_settings = default_settings(ss.perf)
        ss.perf_dirty = False
    ss.setdefault("flash", [])


def reset_revenue(data: RevenueData | None = None, source: str = "synthetic"):
    ss.rev_data = data if data is not None else _synthetic_revenue()
    ss.rev_source = source
    ss.priority_weights = dict(PRIORITY_WEIGHTS_DEFAULT)
    ss.engine_params = dict(ENGINE_DEFAULTS)
    ss.multipliers = {k: v["multiplier"] for k, v in SCENARIOS_DEFAULT.items()}
    ss.scenario = "base"
    opps, _ = opportunities()
    ss.selection = auto_select(opps, compute_kpis(ss.rev_data), 1.0, ss.rev_data.settings.financial_basis)
    ss.sel_version = ss.get("sel_version", 0) + 1


def opportunities():
    """تُحسب من البيانات الحالية في كل تشغيل (سريع)، ثم يُعاد الترتيب بالأوزان الحالية."""
    opps, excluded = detect_opportunities(ss.rev_data, ss.get("engine_params", ENGINE_DEFAULTS))
    opps = score_priority(opps, ss.get("priority_weights", PRIORITY_WEIGHTS_DEFAULT))
    return opps, excluded


def set_perf(perf: PerfData, reason: str = ""):
    ss.perf = perf
    ss.perf_dirty = True
    db = local_db_path()
    if db:
        save_sqlite(perf, db)
        ss.perf_source = "sqlite"


def storage_label() -> str:
    db = local_db_path()
    if db:
        return f"حفظ محلي (SQLite): {db.name}"
    return "ذاكرة الجلسة فقط — صدّر نسخة احتياطية قبل الإغلاق"


def flash(msg: str, kind: str = "success"):
    ss.flash.append((kind, msg))


def show_flash():
    for kind, msg in ss.get("flash", []):
        getattr(st, kind)(msg)
    ss.flash = []
