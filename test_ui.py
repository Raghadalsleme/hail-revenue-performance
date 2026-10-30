"""اختبارات الواجهة عبر Streamlit AppTest: التنقل بين الصفحات وتفاعل العناصر."""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGES = ["revenue", "opportunities", "scenarios", "performance", "perf_entry", "data", "reports", "method"]


@pytest.fixture()
def at():
    a = AppTest.from_file(APP, default_timeout=90)
    a.run()
    assert not a.exception, [e.value for e in a.exception]
    return a


def html_text(a) -> str:
    return " ".join(str(getattr(e, "proto", "")) for e in a.get("html"))


def test_all_pages_render(at):
    for key in PAGES:
        at.radio(key="nav").set_value(key).run()
        assert not at.exception, (key, [e.value for e in at.exception])
        assert at.query_params.get("page") in (key, [key])


def test_revenue_page_shows_gap(at):
    t = html_text(at)
    assert "100,000,000" in t and "20,000,000" in t and "8,500,000" in t


def test_scenario_buttons_change_selection(at):
    at.radio(key="nav").set_value("scenarios").run()
    n_auto = len(at.session_state["selection"])
    assert n_auto > 0
    next(b for b in at.button if b.label == "إلغاء كل الاختيارات").click().run()
    assert at.session_state["selection"] == []
    assert "لم تُختر أي فرصة" in html_text(at) and "الفرص المختارة تغطي" not in html_text(at)
    next(b for b in at.button if b.label == "اختيار الأعلى أولوية تلقائيًا").click().run()
    assert len(at.session_state["selection"]) == n_auto


def test_multiplier_change_updates_state(at):
    at.radio(key="nav").set_value("scenarios").run()
    at.number_input(key="mult_optimistic").set_value(150).run()
    assert at.session_state["multipliers"]["optimistic"] == 1.5
    assert not at.exception


def test_performance_filter_and_settings(at):
    at.radio(key="nav").set_value("performance").run()
    at.selectbox(key="pd_gd").set_value("GD-B").run()
    assert not at.exception
    t = html_text(at)
    assert "قسم الرخص التجريبي" in t and "قسم المتابعة الميدانية" not in t
    at.number_input(key="pw_PLAN").set_value(60).run()  # المجموع 110 => يُرفض
    assert any("مجموع الأوزان" in e.value for e in at.error)
    assert at.session_state["perf_settings"].weights["PLAN"] == 50


def test_revenue_settings_change_target(at):
    at.radio(key="nav").set_value("data").run()
    at.number_input[0].set_value(90_000_000.0)
    next(b for b in at.button if "تطبيق الإعدادات" in b.label).click().run()
    assert at.session_state["rev_data"].settings.annual_target_sar == 90_000_000
    at.radio(key="nav").set_value("revenue").run()
    assert "10,000,000" in html_text(at)  # الفجوة حتى اللقطة بعد تغيير المستهدف


def test_priority_weights_reorder(at):
    at.radio(key="nav").set_value("opportunities").run()
    at.number_input(key="w_contrib").set_value(0).run()
    assert at.session_state["priority_weights"]["contribution"] == 0
    assert not at.exception


def test_month_entry_form_saves_and_blank_stays_missing(at):
    at.radio(key="nav").set_value("perf_entry").run()
    at.selectbox(key="pe_year").set_value(2026).run()
    at.selectbox(key="pe_mon").set_value(9).run()
    key = "pe_GD-A_2026-09_0_D03_QUALITY_actual"
    assert at.number_input(key=key).value is None  # فارغ = غير مدخل
    at.number_input(key=key).set_value(88.0)
    next(b for b in at.button if b.label == "حفظ بيانات الشهر").click().run()
    assert not at.exception
    r = at.session_state["perf"].records
    v = r[(r["dept_id"] == "D03") & (r["month"] == "2026-09") & (r["kpi_id"] == "QUALITY")]["actual"].iloc[0]
    assert v == 88.0
    # بقية الأشهر لم تتغير
    assert len(r[r["month"] == "2026-08"]) == 30  # 18 لـ(أ) + 12 لـ(ب)


def test_month_entry_rejects_zero_target(at):
    at.radio(key="nav").set_value("perf_entry").run()
    at.selectbox(key="pe_year").set_value(2026).run()
    at.selectbox(key="pe_mon").set_value(9).run()
    before = at.session_state["perf"].records.copy()
    at.number_input(key="pe_GD-A_2026-09_0_D01_PLAN_target").set_value(0.0)
    next(b for b in at.button if b.label == "حفظ بيانات الشهر").click().run()
    assert any("أكبر من صفر" in e.value for e in at.error)
    assert at.session_state["perf"].records.equals(before)


def test_rename_department_from_ui_keeps_id(at):
    at.radio(key="nav").set_value("perf_entry").run()
    at.text_input(key="st_nm_GD-A_0_D02").set_value("قسم بعد التعديل")
    next(b for b in at.button if b.label == "حفظ تعديلات الأقسام").click().run()
    d = at.session_state["perf"].depts.set_index("dept_id")
    assert d.at["D02", "dept_name"] == "قسم بعد التعديل"
