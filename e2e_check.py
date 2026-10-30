"""فحص شامل في متصفح حقيقي (Playwright + Chromium) على التطبيق العامل.

يشغّل: التنقل بالنقر على شريط التنقل، أزرار السيناريوهات، نموذج الافتراضات، رفض ملف أداء خاطئ،
وتنزيل PDF وExcel فعليًا. يفشل إذا ظهر أي خطأ Streamlit في أي صفحة.

python scripts/e2e_check.py [عنوان_التطبيق]
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"
NAV = ["لوحة الإيرادات", "فرص الإيرادات", "السيناريوهات", "أداء الإدارات", "إدخال بيانات الأداء", "البيانات والإعدادات", "التقارير", "المنهجية"]
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL"), name, detail)


def no_error(page):
    return page.locator('[data-testid="stException"]').count() == 0 and page.get_by_text("encountered an error").count() == 0


def settle(page, ms=1500):
    page.wait_for_timeout(300)
    page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"] [data-testid=\"stStatusWidgetRunningIcon\"]')", timeout=60000)
    page.wait_for_timeout(ms)


def nav(page, label):
    page.locator('.st-key-topnav [data-testid="stRadioOption"]', has_text=label).first.click()
    settle(page)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1366, "height": 900}, accept_downloads=True, locale="ar-SA")
        page = ctx.new_page()
        page.goto(URL, wait_until="networkidle")
        page.wait_for_selector(".gov-header", timeout=60000)
        settle(page, 2500)
        check("تحميل الصفحة الرئيسية دون أخطاء", no_error(page))
        for label in NAV:
            nav(page, label)
            sel = page.locator('.st-key-topnav [data-testid="stRadioOption"][data-selected="true"]').inner_text().strip()
            check(f"التنقل: {label}", no_error(page) and sel == label and page.locator(".page-head h2").count() == 1, f"المحدد={sel}")

        nav(page, "السيناريوهات")
        page.get_by_role("button", name="إلغاء كل الاختيارات").click()
        settle(page)
        check("زر إلغاء الاختيارات", page.get_by_text("لم تُختر أي فرصة").count() > 0)
        page.get_by_role("button", name="اختيار الأعلى أولوية تلقائيًا").click()
        settle(page)
        check("زر الاختيار التلقائي", page.get_by_text("من الفجوة المتوقعة").count() > 0 and no_error(page))

        nav(page, "البيانات والإعدادات")
        page.get_by_role("button", name="تطبيق الافتراضات").click()
        settle(page)
        check("نموذج افتراضات المحرك", page.get_by_text("طُبّقت الافتراضات").count() > 0 and no_error(page))

        nav(page, "إدخال بيانات الأداء")
        page.get_by_role("tab", name="استيراد ملف CSV أو Excel").click()
        settle(page, 800)
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad_results.csv"
            bad.write_text("dept_id,month,kpi_id,target,actual,data_label\nD01,2026-09,PLAN,90,50,synthetic\nD01,2026-09,PLAN,90,60,synthetic\n", encoding="utf-8")
            page.locator('[data-testid="stFileUploaderDropzoneInput"]').first.set_input_files(str(bad))
            settle(page)
            page.get_by_role("button", name="التحقق من الملف").click()
            settle(page)
            check("رفض ملف أداء مكرر دون تغيير البيانات", page.get_by_text("رُفض الملف ولم تتغير البيانات الحالية").count() > 0 and page.get_by_text("مكررة").count() > 0)

        nav(page, "التقارير")
        page.get_by_role("button", name="إنشاء تقرير PDF").click()
        settle(page, 2500)
        with page.expect_download(timeout=60000) as dl:
            page.get_by_role("button", name="تنزيل تقرير الإيرادات PDF").click()
        data = Path(dl.value.path()).read_bytes()
        check("تنزيل PDF الإيرادات", data[:4] == b"%PDF", f"{len(data):,} بايت")
        page.get_by_role("button", name="إنشاء ملف Excel (النتائج والمدخلات)").click()
        settle(page, 2500)
        with page.expect_download(timeout=60000) as dl:
            page.get_by_role("button", name="تنزيل ملف Excel").click()
        data = Path(dl.value.path()).read_bytes()
        check("تنزيل Excel الإيرادات", data[:2] == b"PK", f"{len(data):,} بايت")
        page.get_by_role("tab", name="تقارير أداء الإدارات").click()
        settle(page, 800)
        with page.expect_download(timeout=60000) as dl:
            page.get_by_role("button", name="تنزيل ملخص الشهر Excel").click()
        data = Path(dl.value.path()).read_bytes()
        check("تنزيل Excel الأداء", data[:2] == b"PK", f"{len(data):,} بايت")
        check("لا أخطاء بعد كل التفاعلات", no_error(page))
        b.close()
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} نجحت")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
