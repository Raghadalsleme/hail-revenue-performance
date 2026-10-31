"""مخططات الجداول (الأعمدة المطلوبة وأنواعها وقيودها) — تُستخدم في الاستيراد والقوالب وقاموس البيانات."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Col:
    name: str
    kind: str  # str | float | int | bool | date | month | label
    desc: str
    nullable: bool = False
    min: float | None = None
    max: float | None = None
    choices: tuple | None = None
    example: str = ""


@dataclass(frozen=True)
class FK:
    col: str
    table: str
    ref_col: str


@dataclass(frozen=True)
class Table:
    key: str
    title: str
    desc: str
    columns: tuple
    id_cols: tuple = ()
    fks: tuple = field(default_factory=tuple)

    @property
    def col_names(self):
        return [c.name for c in self.columns]


LABEL_COL = Col("data_label", "label", "وسم البيانات: synthetic (تجريبية) أو real (حقيقية). لا يُسمح بالخلط داخل المجموعة.", example="synthetic")

# ---------------------------------------------------------------- الإيرادات
REV_SETTINGS = Table(
    key="settings",
    title="إعدادات اللقطة",
    desc="جدول مفتاح/قيمة يحدد السنة المالية والمستهدف وتاريخ اللقطة والأساس المالي.",
    columns=(
        Col("key", "str", "اسم الإعداد"),
        Col("value", "str", "القيمة"),
    ),
    id_cols=("key",),
)
SETTINGS_KEYS = {
    "fiscal_year": "السنة المالية (ميلادية)، مثل 2026",
    "annual_target_sar": "المستهدف السنوي للإيرادات بالريال",
    "snapshot_date": "تاريخ اللقطة YYYY-MM-DD (المحقق حتى هذا التاريخ شاملًا)",
    "financial_basis": "الأساس المالي: cash (نقدي) أو accrual (استحقاق)",
    "data_label": "synthetic أو real",
    "source_note": "وصف مصدر البيانات",
}

REV_SOURCES = Table(
    key="revenue_sources",
    title="مصادر الإيرادات",
    desc="المستهدف والمحقق والمتوقع أصلًا لبقية السنة لكل مصدر إيراد.",
    columns=(
        Col("source_id", "str", "معرف المصدر (فريد)", example="SRC01"),
        Col("source_name", "str", "اسم المصدر", example="رسوم رخص البناء"),
        Col("category", "str", "تصنيف المصدر", example="رسوم"),
        Col("annual_target_sar", "float", "المستهدف السنوي للمصدر (ريال)", min=0),
        Col("realized_to_date_sar", "float", "المحقق (المحصل) حتى تاريخ اللقطة (ريال)", min=0),
        Col("expected_remaining_sar", "float", "الإيراد الأساسي المتوقع أصلًا من تاريخ اللقطة حتى نهاية السنة دون أي فرص جديدة (ريال)، ويشمل دفعات العقود القائمة والتحصيل الاعتيادي", min=0),
        LABEL_COL,
    ),
    id_cols=("source_id",),
)

REV_ASSETS = Table(
    key="assets",
    title="الأصول والأراضي",
    desc="سجل الأصول البلدية وخصائصها وحالة استغلالها والقيود عليها.",
    columns=(
        Col("asset_id", "str", "معرف الأصل (فريد)", example="AST-001"),
        Col("asset_name", "str", "اسم/وصف الأصل"),
        Col("asset_type", "str", "نوع الأصل", choices=("أرض فضاء", "محل تجاري", "مبنى مكاتب", "كشك")),
        Col("district", "str", "الحي/الموقع"),
        Col("location_tier", "str", "فئة الموقع للمرجع السوقي", choices=("A", "B", "C")),
        Col("zoning", "str", "الاستخدام النظامي", choices=("تجاري", "استثماري متعدد", "خدمي", "ترفيهي", "سكني")),
        Col("area_sqm", "float", "المساحة (م²)", min=0.000001),
        Col("frontage_m", "float", "طول الواجهة على الشارع (م)", min=0),
        Col("on_main_road", "bool", "يطل على شارع رئيسي (true/false)"),
        Col("utilities_available", "bool", "الخدمات متوفرة (true/false)"),
        Col("status", "str", "حالة الاستغلال", choices=("غير مستغل", "مستغل جزئيًا", "مستغل")),
        Col("current_occupancy", "float", "نسبة الإشغال الحالية من 0 إلى 1", min=0, max=1),
        Col("current_annual_revenue_sar", "float", "الإيراد السنوي الحالي المدرج ضمن الأساس (ريال)", min=0),
        Col("restricted", "bool", "الأصل مقيد (نزاع، تخصيص لمرفق عام، قيد تخطيطي...)"),
        Col("restriction_reason", "str", "سبب القيد إن وجد", nullable=True),
        LABEL_COL,
    ),
    id_cols=("asset_id",),
)

REV_CONTRACTS = Table(
    key="contracts",
    title="العقود الاستثمارية",
    desc="العقود القائمة على الأصول وقيمها وتواريخ انتهائها وشروط التجديد.",
    columns=(
        Col("contract_id", "str", "معرف العقد (فريد)", example="CTR-1001"),
        Col("asset_id", "str", "الأصل المرتبط (يجب وجوده في جدول الأصول)"),
        Col("source_id", "str", "مصدر الإيراد المرتبط (يجب وجوده في مصادر الإيرادات)"),
        Col("investor_ref", "str", "مرجع المستثمر (رمز وليس اسمًا)"),
        Col("activity", "str", "النشاط"),
        Col("start_date", "date", "تاريخ بداية العقد YYYY-MM-DD"),
        Col("end_date", "date", "تاريخ نهاية العقد YYYY-MM-DD"),
        Col("leased_area_sqm", "float", "المساحة المؤجرة (م²)", min=0.000001),
        Col("annual_value_sar", "float", "القيمة السنوية الحالية للعقد (ريال)", min=0.000001),
        Col("renegotiable", "bool", "هل تسمح الشروط بمراجعة القيمة عند التجديد"),
        Col("max_renewal_increase_pct", "float", "الحد الأعلى التعاقدي للزيادة عند التجديد (0-1)، فارغ إن لا يوجد", nullable=True, min=0, max=1),
        Col("in_dispute", "bool", "العقد محل نزاع"),
        Col("status", "str", "حالة العقد", choices=("ساري", "منتهٍ")),
        LABEL_COL,
    ),
    id_cols=("contract_id",),
    fks=(FK("asset_id", "assets", "asset_id"), FK("source_id", "revenue_sources", "source_id")),
)

REV_RECEIVABLES = Table(
    key="receivables",
    title="المستحقات والتحصيل",
    desc="الفواتير المستحقة والمسدد منها والمتوقع تحصيله أصلًا.",
    columns=(
        Col("invoice_id", "str", "رقم الفاتورة (فريد)", example="INV-50001"),
        Col("debtor_id", "str", "رمز المدين (وليس اسمًا)"),
        Col("debtor_type", "str", "نوع المدين", choices=("مستثمر", "منشأة", "فرد")),
        Col("contract_id", "str", "العقد المرتبط إن وجد", nullable=True),
        Col("source_id", "str", "مصدر الإيراد المرتبط"),
        Col("invoice_date", "date", "تاريخ الفاتورة"),
        Col("due_date", "date", "تاريخ الاستحقاق"),
        Col("amount_due_sar", "float", "المبلغ المستحق (ريال)", min=0.000001),
        Col("amount_paid_sar", "float", "المسدد حتى تاريخ اللقطة (ريال) — يُستبعد من أي فرصة", min=0),
        Col("status", "str", "حالة المطالبة", choices=("عادي", "متأخر", "محل نزاع", "مجدول")),
        Col("expected_baseline_collection_sar", "float", "التحصيل المتوقع أصلًا لبقية السنة ضمن الأساس (ريال)", min=0),
        LABEL_COL,
    ),
    id_cols=("invoice_id",),
    fks=(FK("contract_id", "contracts", "contract_id"), FK("source_id", "revenue_sources", "source_id")),
)

REV_BENCHMARKS = Table(
    key="market_benchmarks",
    title="المراجع السوقية",
    desc="معدلات إيجار سنوية مرجعية حسب فئة الاستخدام وفئة الموقع.",
    columns=(
        Col("benchmark_id", "str", "معرف المرجع (فريد)"),
        Col("category", "str", "فئة الاستخدام", example="أرض تجارية"),
        Col("location_tier", "str", "فئة الموقع", choices=("A", "B", "C")),
        Col("unit", "str", "وحدة القياس", choices=("م²", "لوحة")),
        Col("ref_annual_rate_sar", "float", "المعدل السنوي المرجعي (الوسيط) لكل وحدة", min=0.000001),
        Col("upper_annual_rate_sar", "float", "الحد الأعلى للنطاق المرجعي لكل وحدة", min=0.000001),
        Col("expected_occupancy", "float", "نسبة الإشغال المتوقعة 0-1", min=0, max=1),
        Col("as_of_date", "date", "تاريخ المرجع"),
        Col("source_note", "str", "مصدر المرجع"),
        LABEL_COL,
    ),
    id_cols=("benchmark_id",),
)

REVENUE_TABLES = {t.key: t for t in (REV_SETTINGS, REV_SOURCES, REV_ASSETS, REV_CONTRACTS, REV_RECEIVABLES, REV_BENCHMARKS)}

# ---------------------------------------------------------------- الأداء
PERF_GDS = Table(
    key="general_departments",
    title="الإدارات العامة",
    desc="الإدارات العامة (معرف ثابت لا يتغير عند تغيير الاسم).",
    columns=(
        Col("gd_id", "str", "معرف الإدارة العامة (ثابت)", example="GD-A"),
        Col("gd_name", "str", "اسم الإدارة العامة"),
        Col("active", "bool", "فعالة"),
        LABEL_COL,
    ),
    id_cols=("gd_id",),
)
PERF_DEPTS = Table(
    key="departments",
    title="الأقسام",
    desc="الأقسام التابعة لكل إدارة عامة (معرف ثابت يحفظ التاريخ عند تغيير الاسم).",
    columns=(
        Col("dept_id", "str", "معرف القسم (ثابت)", example="D01"),
        Col("gd_id", "str", "الإدارة العامة التابع لها"),
        Col("dept_name", "str", "اسم القسم"),
        Col("sort_order", "int", "ترتيب العرض", min=0),
        Col("active", "bool", "فعال"),
        LABEL_COL,
    ),
    id_cols=("dept_id",),
    fks=(FK("gd_id", "general_departments", "gd_id"),),
)
PERF_KPIS = Table(
    key="kpi_definitions",
    title="تعريف المؤشرات",
    desc="المؤشرات المعتمدة للتقييم وأوزانها الافتراضية.",
    columns=(
        Col("kpi_id", "str", "معرف المؤشر", example="PLAN"),
        Col("kpi_name", "str", "اسم المؤشر"),
        Col("definition", "str", "التعريف"),
        Col("unit", "str", "الوحدة"),
        Col("default_weight", "float", "الوزن الافتراضي (%)", min=0, max=100),
        Col("min_value", "float", "أقل قيمة مسموحة", min=0),
        Col("max_value", "float", "أعلى قيمة مسموحة", min=0),
    ),
    id_cols=("kpi_id",),
)
PERF_RECORDS = Table(
    key="performance_records",
    title="نتائج الأداء الشهرية",
    desc="صف لكل قسم/شهر/مؤشر: المستهدف والمحقق. الخلية الفارغة = بيانات غير مدخلة (لا تُعامل كصفر).",
    columns=(
        Col("dept_id", "str", "معرف القسم", example="D01"),
        Col("month", "month", "الشهر بصيغة YYYY-MM", example="2026-09"),
        Col("kpi_id", "str", "معرف المؤشر", example="PLAN"),
        Col("target", "float", "المستهدف (0-100)، يجب أن يكون أكبر من صفر", nullable=True, min=0.000001, max=100),
        Col("actual", "float", "المحقق الفعلي خلال الشهر (0-100). اتركه فارغًا إن لم يُدخل", nullable=True, min=0, max=100),
        LABEL_COL,
    ),
    id_cols=("dept_id", "month", "kpi_id"),
    fks=(FK("dept_id", "departments", "dept_id"), FK("kpi_id", "kpi_definitions", "kpi_id")),
)
PERF_TABLES = {t.key: t for t in (PERF_GDS, PERF_DEPTS, PERF_KPIS, PERF_RECORDS)}
