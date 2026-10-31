"""محرك تحقق عام: الأعمدة، الأنواع، القيم السالبة/غير المحدودة، النسب، التكرار، المراجع، وسم البيانات.

القاعدة: لا يُعاد أي جدول "نظيف" إلا إذا خلا من الأخطاء؛ والاستبدال يتم على مستوى المجموعة كاملة
(لا استبدال جزئي)."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import LABEL_REAL, LABEL_SYNTHETIC, VALID_LABELS
from .schemas import Col, Table

TRUE_SET = {"true", "1", "yes", "y", "نعم", "صح", "t"}
FALSE_SET = {"false", "0", "no", "n", "لا", "خطأ", "f"}
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
MAX_ROWS_IN_MSG = 6


@dataclass
class ValidationReport:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def err(self, table_title: str, msg: str):
        self.errors.append(f"[{table_title}] {msg}")

    def warn(self, table_title: str, msg: str):
        self.warnings.append(f"[{table_title}] {msg}")

    def extend(self, other: "ValidationReport"):
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def _rows(idx) -> str:
    """أرقام الصفوف كما تظهر في Excel (الصف 1 للعناوين)."""
    nums = [str(int(i) + 2) for i in list(idx)[:MAX_ROWS_IN_MSG]]
    more = len(idx) - len(nums)
    s = "، ".join(nums)
    return s + (f" (و{more} صفوف أخرى)" if more > 0 else "")


def _blank(series: pd.Series) -> pd.Series:
    return series.isna() | (series.astype(str).str.strip().isin(["", "nan", "NaN", "None", "NaT"]))


def _coerce_col(df: pd.DataFrame, col: Col, t: Table, rep: ValidationReport) -> pd.Series:
    raw = df[col.name]
    blank = _blank(raw)
    if not col.nullable and blank.any():
        rep.err(t.title, f"العمود «{col.name}» فارغ في الصفوف: {_rows(df.index[blank])}")

    if col.kind in ("str", "label"):
        out = pd.Series([None if b else str(v).strip() for v, b in zip(raw, blank)], index=raw.index, dtype=object)
        if col.kind == "label":
            bad = (~blank) & (~out.isin(VALID_LABELS))
            if bad.any():
                rep.err(t.title, f"قيمة غير صحيحة في «data_label» (المسموح synthetic أو real) في الصفوف: {_rows(df.index[bad])}")
        if col.choices:
            bad = (~blank) & (~out.isin(col.choices))
            if bad.any():
                vals = "، ".join(sorted({str(v) for v in out[bad]})[:5])
                rep.err(t.title, f"قيم غير معروفة في «{col.name}» ({vals}) — المسموح: {'، '.join(col.choices)}. الصفوف: {_rows(df.index[bad])}")
        return out

    if col.kind in ("float", "int"):
        num = pd.to_numeric(raw.where(~blank, np.nan), errors="coerce")
        nonnum = (~blank) & num.isna()
        if nonnum.any():
            rep.err(t.title, f"قيم غير رقمية في «{col.name}» في الصفوف: {_rows(df.index[nonnum])}")
        inf = num.map(lambda v: isinstance(v, float) and math.isinf(v))
        if inf.any():
            rep.err(t.title, f"قيم غير محدودة (Infinity) في «{col.name}» في الصفوف: {_rows(df.index[inf])}")
            num = num.where(~inf, np.nan)
        if col.min is not None:
            below = num.notna() & (num < col.min)
            if below.any():
                if col.min == 0:
                    rep.err(t.title, f"قيم سالبة غير مسموحة في «{col.name}» في الصفوف: {_rows(df.index[below])}")
                else:
                    rep.err(t.title, f"قيم أقل من الحد الأدنى ({'أكبر من صفر' if col.min < 1e-3 else col.min}) في «{col.name}» في الصفوف: {_rows(df.index[below])}")
        if col.max is not None:
            above = num.notna() & (num > col.max)
            if above.any():
                rep.err(t.title, f"قيم خارج الحدود (أعلى من {col.max:g}) في «{col.name}» في الصفوف: {_rows(df.index[above])}")
        if col.kind == "int":
            frac = num.notna() & (num % 1 != 0)
            if frac.any():
                rep.err(t.title, f"يجب أن تكون «{col.name}» عددًا صحيحًا في الصفوف: {_rows(df.index[frac])}")
        return num.astype(float)

    if col.kind == "bool":
        def conv(v):
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return None
            if isinstance(v, (bool, np.bool_)):
                return bool(v)
            s = str(v).strip().lower()
            if s in TRUE_SET:
                return True
            if s in FALSE_SET:
                return False
            return "BAD"
        out = raw.map(conv)
        bad = out.astype(str) == "BAD"
        if bad.any():
            rep.err(t.title, f"قيم منطقية غير صحيحة في «{col.name}» (استخدم true/false) في الصفوف: {_rows(df.index[bad])}")
        out = out.astype(object)
        out[bad] = None
        return out

    if col.kind == "date":
        def conv(v):
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return pd.NaT
            if isinstance(v, (pd.Timestamp,)):
                return v.normalize()
            s = str(v).strip()
            if not s:
                return pd.NaT
            try:
                return pd.Timestamp(pd.to_datetime(s, format="%Y-%m-%d")).normalize()
            except (ValueError, TypeError):
                try:
                    ts = pd.to_datetime(s, format="ISO8601")
                    return ts.normalize()
                except (ValueError, TypeError):
                    return "BAD"
        out = raw.map(conv)
        bad = out.map(lambda v: isinstance(v, str))
        if bad.any():
            rep.err(t.title, f"تواريخ غير صالحة في «{col.name}» (الصيغة YYYY-MM-DD) في الصفوف: {_rows(df.index[bad])}")
        out = out.where(~bad, pd.NaT)
        return pd.to_datetime(out)

    if col.kind == "month":
        def conv(v):
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return None
            if isinstance(v, pd.Timestamp):
                return v.strftime("%Y-%m")
            s = str(v).strip()
            if MONTH_RE.match(s):
                return s
            # Excel قد يحول 2026-09 إلى تاريخ كامل
            m = re.match(r"^(\d{4})-(\d{2})-01( 00:00:00)?$", s)
            if m and 1 <= int(m.group(2)) <= 12:
                return f"{m.group(1)}-{m.group(2)}"
            return "BAD"
        out = raw.map(conv)
        bad = out == "BAD"
        if bad.any():
            rep.err(t.title, f"صيغة شهر غير صحيحة في «{col.name}» (المطلوب YYYY-MM) في الصفوف: {_rows(df.index[bad])}")
        out = out.astype(object)
        out[bad] = None
        return out

    raise ValueError(col.kind)


def empty_typed(t: Table) -> pd.DataFrame:
    """جدول فارغ بأنواع أعمدة صحيحة (حتى تعمل العمليات اللاحقة على التواريخ والأرقام)."""
    cols = {}
    for c in t.columns:
        if c.kind in ("float", "int"):
            cols[c.name] = pd.Series(dtype=float)
        elif c.kind == "date":
            cols[c.name] = pd.Series(dtype="datetime64[ns]")
        else:
            cols[c.name] = pd.Series(dtype=object)
    return pd.DataFrame(cols)


def validate_table(df: pd.DataFrame | None, t: Table, required: bool = True, allow_empty: bool = False) -> tuple[pd.DataFrame | None, ValidationReport]:
    rep = ValidationReport()
    if df is None:
        if required:
            rep.err(t.title, f"الجدول مفقود (المتوقع ورقة/ملف باسم «{t.key}»)")
        return None, rep
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in t.col_names if c not in df.columns]
    if missing:
        rep.err(t.title, "أعمدة مطلوبة مفقودة: " + "، ".join(missing))
        return None, rep
    df = df[t.col_names]
    # تجاهل الصفوف الفارغة تمامًا
    empty_rows = df.apply(lambda r: _blank(r).all(), axis=1)
    df = df[~empty_rows].reset_index(drop=True)
    if df.empty:
        if allow_empty:
            rep.warn(t.title, "الجدول فارغ")
            return empty_typed(t), rep
        rep.err(t.title, "الجدول لا يحتوي أي صفوف")
        return None, rep
    out = pd.DataFrame(index=df.index)
    for col in t.columns:
        out[col.name] = _coerce_col(df, col, t, rep)
    if t.id_cols:
        dup = out.duplicated(subset=list(t.id_cols), keep=False)
        if dup.any():
            keys = out.loc[dup, list(t.id_cols)].astype(str).agg(" / ".join, axis=1)
            sample = "، ".join(sorted(set(keys))[:5])
            what = "المعرف" if len(t.id_cols) == 1 else "المفتاح (" + " + ".join(t.id_cols) + ")"
            rep.err(t.title, f"قيم مكررة في {what}: {sample} — الصفوف: {_rows(out.index[dup])}")
    if not rep.ok:
        return None, rep
    return out, rep


def check_fks(tables: dict, specs: dict, rep: ValidationReport):
    for key, t in specs.items():
        df = tables.get(key)
        if df is None:
            continue
        for fk in t.fks:
            ref = tables.get(fk.table)
            if ref is None:
                continue
            vals = df[fk.col]
            present = vals.notna()
            bad = present & ~vals.isin(set(ref[fk.ref_col]))
            if bad.any():
                sample = "، ".join(sorted({str(v) for v in vals[bad]})[:5])
                rep.err(t.title, f"مراجع غير موجودة: «{fk.col}» = {sample} غير موجود في «{specs[fk.table].title}». الصفوف: {_rows(df.index[bad])}")


def check_labels(tables: dict, specs: dict, rep: ValidationReport, demo: bool, extra_labels: set | None = None) -> str | None:
    """يمنع خلط البيانات الحقيقية والتجريبية داخل الجدول وداخل المجموعة. يعيد الوسم الموحد."""
    found = set(extra_labels or set())
    for key, df in tables.items():
        if df is None or "data_label" not in df.columns:
            continue
        labels = set(df["data_label"].dropna().unique())
        if len(labels) > 1:
            rep.err(specs[key].title, "خلط بيانات حقيقية وتجريبية داخل الجدول نفسه (data_label)")
        found |= labels
    if len(found) > 1:
        rep.err("المجموعة", "خلط بيانات حقيقية (real) وتجريبية (synthetic) داخل مجموعة البيانات نفسها — يجب أن تكون المجموعة كلها من نوع واحد")
        return None
    label = next(iter(found)) if found else None
    if demo and label == LABEL_REAL:
        rep.err("المجموعة", "هذه نسخة عرض منشورة وتقبل البيانات التجريبية (synthetic) فقط. لتحليل بيانات حقيقية شغّل النظام داخليًا مع HAIL_DEMO_MODE=0")
    return label


def read_any(file_or_path, name: str | None = None) -> dict:
    """يقرأ CSV أو Excel ويعيد قاموس {اسم الجدول: DataFrame}. كل القيم تُقرأ كنصوص للتحقق لاحقًا."""
    fname = name or getattr(file_or_path, "name", str(file_or_path))
    lower = fname.lower()
    if lower.endswith((".xlsx", ".xlsm", ".xls")):
        sheets = pd.read_excel(file_or_path, sheet_name=None, dtype=object)
        return {str(k).strip(): v for k, v in sheets.items()}
    if lower.endswith(".csv"):
        df = pd.read_csv(file_or_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        stem = re.sub(r"\.csv$", "", fname.split("/")[-1], flags=re.I)
        return {stem.strip(): df}
    raise ValueError(f"صيغة ملف غير مدعومة: {fname} (المدعوم: CSV أو Excel)")
