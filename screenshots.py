"""يلتقط صورًا من التطبيق العامل (يتطلب تشغيل التطبيق أولًا على المنفذ 8501 وتثبيت Playwright Chromium).

python scripts/screenshots.py [عنوان_التطبيق] [مجلد_الحفظ]
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "screenshots")
PAGES = ["revenue", "opportunities", "scenarios", "performance", "perf_entry", "data", "reports", "method"]
VIEWPORTS = {"desktop": (1366, 768), "mobile": (390, 844)}


def wait_ready(page):
    page.wait_for_selector(".gov-header", timeout=60000)
    page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]') || document.querySelectorAll('[data-testid=\"stSkeleton\"]').length === 0", timeout=60000)
    page.wait_for_timeout(2500)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for vname, (w, h) in VIEWPORTS.items():
            ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1 if vname == "desktop" else 2, locale="ar-SA")
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            for key in (PAGES if vname == "desktop" else ["revenue", "opportunities", "performance", "scenarios"]):
                page.goto(f"{URL}/?page={key}", wait_until="networkidle")
                wait_ready(page)
                page.screenshot(path=str(OUT / f"{vname}_{key}_top.png"))
                ov = page.evaluate("() => { const m = document.querySelector('[data-testid=\"stMain\"]'); return Math.max(document.documentElement.scrollWidth - document.documentElement.clientWidth, m ? m.scrollWidth - m.clientWidth : 0); }")
                # Streamlit يمرر المحتوى داخل حاوية داخلية؛ لالتقاط الصفحة كاملة نكبّر ارتفاع النافذة مؤقتًا
                full_h = page.evaluate("() => { const m = document.querySelector('[data-testid=\"stMain\"]'); return m ? m.scrollHeight : document.body.scrollHeight; }")
                page.set_viewport_size({"width": w, "height": min(int(full_h) + 40, 12000)})
                page.wait_for_timeout(1800)
                page.screenshot(path=str(OUT / f"{vname}_{key}_full.png"))
                page.set_viewport_size({"width": w, "height": h})
                print(vname, key, "horizontal-overflow-px:", ov, "page-height:", full_h)
            print(vname, "page errors:", errors[:3])
            ctx.close()
        b.close()


if __name__ == "__main__":
    main()
