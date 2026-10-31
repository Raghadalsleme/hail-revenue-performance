"""ثوابت وإعدادات افتراضية للمنصة. كل القيم هنا افتراضات تجريبية قابلة للتعديل."""
from __future__ import annotations

import os
from pathlib import Path

APP_VERSION = "2.0.0"
APP_NAME_AR = "منصة تنمية الإيرادات البلدية ومتابعة أداء الإدارات"
APP_NAME_EN = "Smart Municipal Revenue Growth & Department Performance System"
ORG_NAME_AR = "أمانة منطقة حائل"
ORG_NAME_EN = "Hail Region Municipality"

SYNTHETIC_NOTICE = "Synthetic Data — بيانات تجريبية لا تمثل أرقام أمانة منطقة حائل"
PROTOTYPE_NOTICE = "نموذج أولي للعرض — غير معتمد رسميًا من أمانة منطقة حائل"

LABEL_SYNTHETIC = "synthetic"
LABEL_REAL = "real"
VALID_LABELS = {LABEL_SYNTHETIC, LABEL_REAL}

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "synthetic"
TEMPLATES_DIR = ROOT / "templates"
FONTS_DIR = ROOT / "assets" / "fonts"
LOGO_DIR = ROOT / "assets" / "logo"


def demo_mode() -> bool:
    """وضع العرض: مفعّل افتراضيًا (للنسخة المنشورة) ويرفض أي بيانات موسومة كحقيقية.
    للتشغيل المحلي على بيانات حقيقية: HAIL_DEMO_MODE=0"""
    return os.environ.get("HAIL_DEMO_MODE", "1").strip() not in {"0", "false", "False", "no"}


def local_db_path() -> Path | None:
    """حفظ محلي اختياري لبيانات الأداء في SQLite (للتشغيل المحلي فقط).
    يُفعّل بتعيين HAIL_LOCAL_DB إلى مسار ملف، مثل data/local/performance.db"""
    p = os.environ.get("HAIL_LOCAL_DB", "").strip()
    return Path(p) if p else None


# ---------- محرك الفرص: افتراضات قابلة للتعديل ----------
ENGINE_DEFAULTS = {
    # العقود "القريبة من التجديد": تنتهي خلال هذه المدة من تاريخ اللقطة
    "renewal_window_days": 365,
    # يُعد العقد أقل من المرجع إذا كانت قيمته أقل من المرجع بهذه النسبة أو أكثر
    "underpricing_threshold": 0.10,
    # مهلة تحضير مراجعة التجديد (تقييم + تفاوض + اعتماد)
    "renewal_lead_days": 45,
    # المستحقات: الحد الأدنى للتأخير لاعتبارها فرصة تحصيل
    "min_overdue_days": 90,
    # مدة حملة التحصيل التي بُنيت عليها نسب الاسترداد
    "collection_campaign_days": 120,
    "collection_lead_days": 15,
    # نسب استرداد مفترضة خلال مدة الحملة حسب عمر الدين
    "recovery_rates": {"90-180": 0.50, "181-365": 0.35, "365+": 0.20},
    # المدينون الأقل من هذا الرصيد يُجمعون في حملة تحصيل جماعية واحدة
    "pool_threshold_sar": 150_000,
    # مهلة إضافية عند عدم توفر الخدمات في الأرض
    "no_utilities_extra_days": 60,
}

# أوزان ترتيب الأولوية (تجريبية)
PRIORITY_WEIGHTS_DEFAULT = {"contribution": 50, "ease": 30, "risk": 20}

# معاملات الحساسية للسيناريوهات (افتراضات وليست فواصل ثقة)
SCENARIOS_DEFAULT = {
    "conservative": {"label": "متحفظ", "multiplier": 0.70},
    "base": {"label": "متوسط", "multiplier": 1.00},
    "optimistic": {"label": "متفائل", "multiplier": 1.20},
}

# ---------- الأداء ----------
PERF_THRESHOLDS_DEFAULT = {"green": 90.0, "yellow": 70.0}

STATUS_META = {
    "good": {"label": "جيد", "color": "#1F7A3A", "bg": "#E9F4EC", "border": "#B9DCC3"},
    "medium": {"label": "متوسط", "color": "#8A5A00", "bg": "#FBF3E0", "border": "#EBD3A0"},
    "intervene": {"label": "يحتاج تدخل", "color": "#B42318", "bg": "#FBECEA", "border": "#F0C2BD"},
    "incomplete": {"label": "بيانات ناقصة", "color": "#4B5563", "bg": "#F1F2F4", "border": "#D3D7DD"},
}
# ألوان الحالة في الرسوم (مختلفة عن ألوان السلاسل)
STATUS_FILL = {"good": "#2E9B4F", "medium": "#E2A72E", "intervene": "#D2463B", "incomplete": "#B8BEC6"}

# ألوان سلاسل الرسوم (ترتيب ثابت، مأخوذ من لوحة ألوان مُتحقق منها لعمى الألوان)
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]

BRAND = {
    "green": "#0E5A43",
    "green_600": "#137255",
    "green_50": "#EAF3EF",
    "gold": "#A9853A",
    "ink": "#17211D",
    "muted": "#5A6660",
    "line": "#DCE3DF",
    "bg": "#F4F6F5",
    "target_gray": "#C9D1CD",
}
