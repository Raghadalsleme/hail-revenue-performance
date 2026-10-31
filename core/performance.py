"""متابعة أداء الأقسام شهريًا: الحساب والتصنيف والمقارنة، وإدارة الإدارات والأقسام والإدخال والاستيراد.

قواعد أساسية:
- تحقيق المؤشر = المحقق ÷ المستهدف × 100 بسقف 100% (تجاوز مستهدف لا يعوض ضعف مؤشر آخر).
- درجة القسم = المتوسط المرجح لتحقيق المؤشرات (تُقرّب لمنزلتين قبل التصنيف).
- القيمة المفقودة ليست صفرًا: نقص أي مدخل مطلوب ⇒ «بيانات ناقصة» (رمادي) دون درجة.
- المقارنة مع الشهر التقويمي السابق فقط، وفقط إذا كانت بياناته مكتملة.
- لوحة متابعة وليست أداة لاتخاذ قرارات أو جزاءات بحق الموظفين.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DATA_DIR, PERF_THRESHOLDS_DEFAULT, STATUS_META, demo_mode
from .formatting import fmt_pct, month_label
from .schemas import PERF_DEPTS, PERF_GDS, PERF_KPIS, PERF_RECORDS, PERF_TABLES
from .validation import ValidationReport, check_fks, check_labels, read_any, validate_table


@dataclass(frozen=True)
class PerfData:
    gds: pd.DataFrame
    depts: pd.DataFrame
    kpis: pd.DataFrame
    records: pd.DataFrame

    def tables(self) -> dict:
        return {"general_departments": self.gds, "departments": self.depts, "kpi_definitions": self.kpis, "performance_records": self.records}

    @property
    def label(self) -> str | None:
        labels = set()
        for df in (self.gds, self.depts, self.records):
            if "data_label" in df.columns:
                labels |= set(df["data_label"].dropna())
        return next(iter(labels)) if len(labels) == 1 else None


@dataclass(frozen=True)
class PerfSettings:
    weights: dict  # kpi_id -> وزن %
    green: float = PERF_THRESHOLDS_DEFAULT["green"]
    yellow: float = PERF_THRESHOLDS_DEFAULT["yellow"]

    def validate(self) -> list[str]:
        errs = []
        tot = sum(float(v) for v in self.weights.values())
        if abs(tot - 100) > 1e-6:
            errs.append(f"مجموع الأوزان يجب أن يساوي 100% (الحالي {tot:g}%)")
        if any(float(v) < 0 for v in self.weights.values()):
            errs.append("لا يُسمح بأوزان سالبة")
        if not 0 < self.yellow < self.green <= 100:
            errs.append("يجب أن يكون: 0 < حد «متوسط» < حد «جيد» ≤ 100")
        return errs


def default_settings(perf: PerfData) -> PerfSettings:
    return PerfSettings(weights={r.kpi_id: float(r.default_weight) for r in perf.kpis.itertuples()})


# ------------------------------------------------------------------ الحساب
def kpi_achievement(target, actual) -> float | None:
    """None إذا كان أي مدخل مفقودًا أو كان المستهدف غير صالح (≤ 0). الصفر الفعلي يعطي 0."""
    if target is None or actual is None:
        return None
    try:
        t, a = float(target), float(actual)
    except (TypeError, ValueError):
        return None
    if np.isnan(t) or np.isnan(a) or t <= 0:
        return None
    return min(a / t * 100.0, 100.0)


def classify(score: float | None, s: PerfSettings) -> str:
    if score is None:
        return "incomplete"
    if score >= s.green:
        return "good"
    if score >= s.yellow:
        return "medium"
    return "intervene"


def prev_month(month: str) -> str:
    y, m = map(int, month.split("-"))
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def _dept_month(perf: PerfData, dept_id: str, month: str, s: PerfSettings) -> dict:
    kpis = perf.kpis
    rec = perf.records[(perf.records["dept_id"] == dept_id) & (perf.records["month"] == month)].set_index("kpi_id")
    details, missing = [], []
    wsum, acc = 0.0, 0.0
    for k in kpis.itertuples():
        w = float(s.weights.get(k.kpi_id, 0))
        tgt = rec.at[k.kpi_id, "target"] if k.kpi_id in rec.index else None
        act = rec.at[k.kpi_id, "actual"] if k.kpi_id in rec.index else None
        tgt = None if tgt is None or (isinstance(tgt, float) and np.isnan(tgt)) else float(tgt)
        act = None if act is None or (isinstance(act, float) and np.isnan(act)) else float(act)
        ach = kpi_achievement(tgt, act)
        if w > 0 and ach is None:
            if tgt is None and act is None:
                missing.append(f"المستهدف والمحقق لـ«{k.kpi_name}»")
            elif tgt is None or tgt <= 0:
                missing.append(f"المستهدف لـ«{k.kpi_name}»" if tgt is None else f"مستهدف غير صالح لـ«{k.kpi_name}»")
            else:
                missing.append(f"المحقق لـ«{k.kpi_name}»")
        if ach is not None:
            wsum += w
            acc += w * ach
        details.append({
            "kpi_id": k.kpi_id, "kpi_name": k.kpi_name, "definition": k.definition, "unit": k.unit, "weight": w,
            "target": tgt, "actual": act, "achievement": ach,
            "weighted": (w * ach / 100.0) if ach is not None else None,
            "met": (act is not None and tgt is not None and act >= tgt),
            "raw_ratio": (act / tgt * 100) if (act is not None and tgt and tgt > 0) else None,
        })
    no_data = rec.empty
    complete = not missing and wsum > 0
    score = round(acc / wsum, 2) if complete else None
    return {"score": score, "complete": complete, "missing": missing, "details": details, "no_data": no_data}


def month_summary(perf: PerfData, gd_id: str, month: str, s: PerfSettings) -> pd.DataFrame:
    """ملخص الأقسام الفعالة التابعة لإدارة عامة في شهر محدد مع المقارنة بالشهر السابق."""
    depts = perf.depts[(perf.depts["gd_id"] == gd_id) & (perf.depts["active"].astype(bool))].sort_values(["sort_order", "dept_id"])
    pm = prev_month(month)
    rows = []
    for d in depts.itertuples():
        cur = _dept_month(perf, d.dept_id, month, s)
        prv = _dept_month(perf, d.dept_id, pm, s)
        status = classify(cur["score"], s)
        unmet = [x["kpi_name"] for x in cur["details"] if x["actual"] is not None and x["target"] is not None and not x["met"]]
        if status == "incomplete":
            reason = "لا توجد بيانات مدخلة لهذا الشهر" if cur["no_data"] else "بيانات ناقصة: " + "، ".join(cur["missing"])
        else:
            weakest = min((x for x in cur["details"] if x["achievement"] is not None and x["weight"] > 0), key=lambda x: x["achievement"])
            if status == "good":
                reason = f"الدرجة {cur['score']:.1f}% ≥ حد «جيد» ({s.green:g}%)"
            elif status == "medium":
                reason = f"الدرجة {cur['score']:.1f}% بين {s.yellow:g}% و{s.green:g}%؛ أضعف مؤشر: {weakest['kpi_name']} ({weakest['achievement']:.1f}%)"
            else:
                reason = f"الدرجة {cur['score']:.1f}% أقل من {s.yellow:g}%؛ أضعف مؤشر: {weakest['kpi_name']} ({weakest['achievement']:.1f}%)"
            zero = [x["kpi_name"] for x in cur["details"] if x["actual"] == 0]
            if zero:
                reason += " — يوجد محقق صفري فعلي في: " + "، ".join(zero)
        if cur["complete"] and prv["complete"]:
            delta = round(cur["score"] - prv["score"], 2)
            cmp_note = f"مقارنة بـ{month_label(pm)}"
        else:
            delta = None
            if not cur["complete"]:
                cmp_note = "لا مقارنة: بيانات الشهر الحالي غير مكتملة"
            elif prv["no_data"]:
                cmp_note = f"لا تتوفر مقارنة: لا توجد بيانات لـ{month_label(pm)}"
            else:
                cmp_note = f"لا تتوفر مقارنة: بيانات {month_label(pm)} غير مكتملة"
        rows.append({
            "dept_id": d.dept_id, "dept_name": d.dept_name, "sort_order": d.sort_order,
            "score": cur["score"], "status": status, "status_label": STATUS_META[status]["label"],
            "reason": reason, "unmet": unmet, "missing": cur["missing"], "details": cur["details"],
            "prev_month": pm, "prev_score": prv["score"], "delta": delta, "compare_note": cmp_note,
        })
    return pd.DataFrame(rows)


def gd_kpis(summary: pd.DataFrame) -> dict:
    n = len(summary)
    comp = summary[summary["status"] != "incomplete"] if n else summary
    return {
        "n_depts": n,
        "avg_score": float(comp["score"].mean()) if len(comp) else None,
        "n_intervene": int((summary["status"] == "intervene").sum()) if n else 0,
        "n_medium": int((summary["status"] == "medium").sum()) if n else 0,
        "n_good": int((summary["status"] == "good").sum()) if n else 0,
        "n_complete": len(comp),
        "n_incomplete": n - len(comp),
        "complete_pct": (len(comp) / n * 100) if n else None,
    }


def months_range(perf: PerfData, gd_id: str) -> list[str]:
    """كل الأشهر التقويمية من أول شهر إلى آخر شهر لديه بيانات (تشمل الأشهر الفارغة)."""
    ids = set(perf.depts.loc[perf.depts["gd_id"] == gd_id, "dept_id"])
    ms = sorted(set(perf.records.loc[perf.records["dept_id"].isin(ids), "month"]))
    if not ms:
        return []
    out, cur = [], ms[0]
    while cur <= ms[-1]:
        out.append(cur)
        y, m = map(int, cur.split("-"))
        cur = f"{y + 1}-01" if m == 12 else f"{y}-{m + 1:02d}"
    return out


def trend(perf: PerfData, gd_id: str, s: PerfSettings) -> pd.DataFrame:
    """اتجاه الدرجات (NaN للأشهر غير المكتملة/غير المدخلة — لا تُوصل في الرسم)."""
    months = months_range(perf, gd_id)
    depts = perf.depts[(perf.depts["gd_id"] == gd_id) & (perf.depts["active"].astype(bool))].sort_values(["sort_order", "dept_id"])
    rows = []
    for d in depts.itertuples():
        for m in months:
            r = _dept_month(perf, d.dept_id, m, s)
            st = classify(r["score"], s)
            rows.append({"dept_id": d.dept_id, "dept_name": d.dept_name, "month": m, "score": r["score"], "status": st, "no_data": r["no_data"]})
    return pd.DataFrame(rows, columns=["dept_id", "dept_name", "month", "score", "status", "no_data"])


# ------------------------------------------------------------------ التحميل والتحقق
def _read_dir(d: Path) -> dict:
    return {k: pd.read_csv(Path(d) / f"{k}.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig") for k in PERF_TABLES}


def validate_perf_bundle(raw: dict, demo: bool | None = None) -> tuple[PerfData | None, ValidationReport]:
    """تحقق من مجموعة أداء كاملة (إدارات + أقسام + مؤشرات + نتائج)."""
    demo = demo_mode() if demo is None else demo
    rep = ValidationReport()
    clean = {}
    for k, spec in PERF_TABLES.items():
        df, r = validate_table(raw.get(k), spec, allow_empty=(k == "performance_records"))
        rep.extend(r)
        clean[k] = df
    if not rep.ok:
        return None, rep
    _post_checks(clean, rep, demo)
    if not rep.ok:
        return None, rep
    return PerfData(clean["general_departments"], clean["departments"], clean["kpi_definitions"], clean["performance_records"]), rep


def _post_checks(clean: dict, rep: ValidationReport, demo: bool, extra_labels: set | None = None):
    check_fks(clean, PERF_TABLES, rep)
    check_labels({k: clean[k] for k in ("general_departments", "departments", "performance_records") if clean.get(k) is not None}, PERF_TABLES, rep, demo, extra_labels)
    k = clean.get("kpi_definitions")
    if k is not None:
        bad = k["max_value"] < k["min_value"]
        if bad.any():
            rep.err(PERF_KPIS.title, "الحد الأعلى أقل من الحد الأدنى لبعض المؤشرات")
        if abs(float(k["default_weight"].sum()) - 100) > 1e-6:
            rep.err(PERF_KPIS.title, "مجموع الأوزان الافتراضية يجب أن يساوي 100")
    recs = clean.get("performance_records")
    if recs is not None and k is not None:
        lim = k.set_index("kpi_id")
        for col in ("target", "actual"):
            mx = recs["kpi_id"].map(lim["max_value"])
            mn = recs["kpi_id"].map(lim["min_value"])
            bad = recs[col].notna() & ((recs[col] > mx) | (recs[col] < mn))
            if bad.any():
                rep.err(PERF_RECORDS.title, f"قيم «{col}» خارج حدود المؤشر في الصفوف: " + "، ".join(str(i + 2) for i in recs.index[bad][:6]))
        both_blank = recs["target"].isna() & recs["actual"].isna()
        if both_blank.any():
            rep.warn(PERF_RECORDS.title, f"{int(both_blank.sum())} صف بلا مستهدف ولا محقق — سيُعامل كبيانات غير مدخلة")


def load_synthetic_perf(d: Path = DATA_DIR) -> PerfData:
    perf, rep = validate_perf_bundle(_read_dir(d), demo=True)
    if perf is None:
        raise RuntimeError("بيانات الأداء التجريبية غير صالحة: " + " | ".join(rep.errors))
    return perf


def merge_records_upload(perf: PerfData, raw: dict, demo: bool | None = None) -> tuple[PerfData | None, ValidationReport, dict]:
    """استيراد نتائج شهرية (مع/دون جداول الهيكل). يتحقق من الملف كاملًا ثم يدمج:
    الصفوف المرفوعة تستبدل نفس (القسم، الشهر) في البيانات الحالية، وما عداها يبقى كما هو.
    إذا تضمن الملف جداول الإدارات/الأقسام فإنها تُدمج بمعرفاتها (تحديث الاسم دون فقد التاريخ)."""
    demo = demo_mode() if demo is None else demo
    rep = ValidationReport()
    info = {}
    if "performance_records" not in raw:
        # ملف CSV واحد بأي اسم يُعامل كجدول النتائج
        if len(raw) == 1:
            raw = {"performance_records": next(iter(raw.values()))}
        else:
            rep.err("الملف", "لم يُعثر على ورقة «performance_records» في الملف")
            return None, rep, info
    gds, depts = perf.gds, perf.depts
    for key, spec in (("general_departments", PERF_GDS), ("departments", PERF_DEPTS)):
        if key in raw:
            df, r = validate_table(raw[key], spec)
            rep.extend(r)
            if df is not None:
                base = gds if key == "general_departments" else depts
                idc = spec.id_cols[0]
                merged = pd.concat([base[~base[idc].isin(df[idc])], df], ignore_index=True)
                if key == "general_departments":
                    gds = merged
                else:
                    depts = merged
    recs, r = validate_table(raw["performance_records"], PERF_RECORDS)
    rep.extend(r)
    if not rep.ok:
        return None, rep, info
    blank = recs["target"].isna() & recs["actual"].isna()
    recs = recs[~blank].reset_index(drop=True)
    if recs.empty:
        rep.err(PERF_RECORDS.title, "لا توجد قيم مدخلة في الملف (كل الصفوف بلا مستهدف ولا محقق)")
        return None, rep, info
    clean = {"general_departments": gds, "departments": depts, "kpi_definitions": perf.kpis, "performance_records": recs}
    _post_checks(clean, rep, demo, extra_labels=({perf.label} if perf.label else set()))
    if not rep.ok:
        return None, rep, info
    keys = set(zip(recs["dept_id"], recs["month"]))
    old = perf.records
    mask = pd.Series([(d, m) in keys for d, m in zip(old["dept_id"], old["month"])], index=old.index)
    info = {"rows": len(recs), "dept_months": len(keys), "replaced_rows": int(mask.sum()), "months": sorted({m for _, m in keys})}
    new_records = pd.concat([old[~mask], recs], ignore_index=True).sort_values(["dept_id", "month", "kpi_id"]).reset_index(drop=True)
    return PerfData(gds, depts, perf.kpis, new_records), rep, info


def read_perf_files(files) -> dict:
    raw = {}
    for f in files:
        raw.update(read_any(f))
    return raw


# ------------------------------------------------------------------ تعديل الهيكل والإدخال
def rename_gd(perf: PerfData, gd_id: str, name: str) -> PerfData:
    name = name.strip()
    if not name:
        raise ValueError("اسم الإدارة العامة لا يمكن أن يكون فارغًا")
    g = perf.gds.copy()
    g.loc[g["gd_id"] == gd_id, "gd_name"] = name
    return replace(perf, gds=g)


def add_gd(perf: PerfData, name: str) -> tuple[PerfData, str]:
    name = name.strip()
    if not name:
        raise ValueError("اسم الإدارة العامة لا يمكن أن يكون فارغًا")
    existing = set(perf.gds["gd_id"])
    i = len(existing) + 1
    while f"GD-{i:02d}" in existing:
        i += 1
    gid = f"GD-{i:02d}"
    row = pd.DataFrame([{"gd_id": gid, "gd_name": name, "active": True, "data_label": perf.label or "synthetic"}])
    return replace(perf, gds=pd.concat([perf.gds, row], ignore_index=True)), gid


def add_dept(perf: PerfData, gd_id: str, name: str) -> tuple[PerfData, str]:
    name = name.strip()
    if not name:
        raise ValueError("اسم القسم لا يمكن أن يكون فارغًا")
    if gd_id not in set(perf.gds["gd_id"]):
        raise ValueError("الإدارة العامة غير موجودة")
    nums = [int(x[1:]) for x in perf.depts["dept_id"] if x.startswith("D") and x[1:].isdigit()]
    did = f"D{(max(nums) + 1 if nums else 1):02d}"
    order = int(perf.depts.loc[perf.depts["gd_id"] == gd_id, "sort_order"].max() or 0) + 1 if (perf.depts["gd_id"] == gd_id).any() else 1
    row = pd.DataFrame([{"dept_id": did, "gd_id": gd_id, "dept_name": name, "sort_order": float(order), "active": True, "data_label": perf.label or "synthetic"}])
    return replace(perf, depts=pd.concat([perf.depts, row], ignore_index=True)), did


def update_depts(perf: PerfData, edits: pd.DataFrame) -> PerfData:
    """تحديث الاسم/الترتيب/الحالة بالمعرف الثابت (لا يتغير المعرف فيبقى التاريخ مرتبطًا)."""
    d = perf.depts.copy().set_index("dept_id")
    for r in edits.itertuples():
        if r.dept_id not in d.index:
            raise ValueError(f"قسم غير موجود: {r.dept_id}")
        nm = str(r.dept_name).strip()
        if not nm:
            raise ValueError(f"اسم القسم {r.dept_id} لا يمكن أن يكون فارغًا")
        d.at[r.dept_id, "dept_name"] = nm
        d.at[r.dept_id, "sort_order"] = float(r.sort_order)
        d.at[r.dept_id, "active"] = bool(r.active)
    return replace(perf, depts=d.reset_index()[perf.depts.columns])


def upsert_month(perf: PerfData, month: str, wide: pd.DataFrame) -> tuple[PerfData | None, list[str]]:
    """حفظ إدخال شهر من جدول عريض: dept_id + {kpi}_target + {kpi}_actual.
    الخلية الفارغة تبقى «غير مدخلة» ولا تتحول إلى صفر. يستبدل صفوف هذه الأقسام لهذا الشهر فقط."""
    errs = []
    import re as _re
    if not _re.match(r"^\d{4}-(0[1-9]|1[0-2])$", str(month)):
        return None, ["صيغة الشهر غير صحيحة (YYYY-MM)"]
    lim = perf.kpis.set_index("kpi_id")
    rows = []
    for r in wide.itertuples(index=False):
        rd = r._asdict()
        for k in lim.index:
            t, a = rd.get(f"{k}_target"), rd.get(f"{k}_actual")
            t = None if t is None or (isinstance(t, float) and np.isnan(t)) else float(t)
            a = None if a is None or (isinstance(a, float) and np.isnan(a)) else float(a)
            if t is None and a is None:
                continue
            for nm, v in (("المستهدف", t), ("المحقق", a)):
                if v is not None and (np.isinf(v) or v < lim.at[k, "min_value"] or v > lim.at[k, "max_value"]):
                    errs.append(f"{rd['dept_id']}: {nm} لـ«{lim.at[k, 'kpi_name']}» خارج الحدود ({lim.at[k, 'min_value']:g}–{lim.at[k, 'max_value']:g})")
            if t is not None and t <= 0:
                errs.append(f"{rd['dept_id']}: المستهدف لـ«{lim.at[k, 'kpi_name']}» يجب أن يكون أكبر من صفر")
            rows.append({"dept_id": rd["dept_id"], "month": month, "kpi_id": k, "target": t, "actual": a, "data_label": perf.label or "synthetic"})
    if errs:
        return None, errs
    ids = set(wide["dept_id"])
    old = perf.records
    keep = old[~((old["dept_id"].isin(ids)) & (old["month"] == month))]
    new = pd.concat([keep, pd.DataFrame(rows, columns=old.columns)], ignore_index=True).sort_values(["dept_id", "month", "kpi_id"]).reset_index(drop=True)
    new["target"] = new["target"].astype(float)
    new["actual"] = new["actual"].astype(float)
    return replace(perf, records=new), []


def month_wide(perf: PerfData, gd_id: str, month: str) -> pd.DataFrame:
    depts = perf.depts[(perf.depts["gd_id"] == gd_id) & (perf.depts["active"].astype(bool))].sort_values(["sort_order", "dept_id"])
    rec = perf.records[perf.records["month"] == month]
    out = []
    for d in depts.itertuples():
        row = {"dept_id": d.dept_id, "dept_name": d.dept_name}
        sub = rec[rec["dept_id"] == d.dept_id].set_index("kpi_id")
        for k in perf.kpis["kpi_id"]:
            row[f"{k}_target"] = float(sub.at[k, "target"]) if k in sub.index and pd.notna(sub.at[k, "target"]) else np.nan
            row[f"{k}_actual"] = float(sub.at[k, "actual"]) if k in sub.index and pd.notna(sub.at[k, "actual"]) else np.nan
        out.append(row)
    return pd.DataFrame(out)


# ------------------------------------------------------------------ حفظ محلي اختياري (SQLite)
def save_sqlite(perf: PerfData, path: Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    with sqlite3.connect(tmp) as con:
        for k, df in perf.tables().items():
            df.to_sql(k, con, index=False)
    tmp.replace(path)  # استبدال ذري: لا ملف نصف مكتوب


def load_sqlite(path: Path) -> PerfData | None:
    path = Path(path)
    if not path.exists():
        return None
    with sqlite3.connect(path) as con:
        raw = {k: pd.read_sql(f"SELECT * FROM {k}", con).astype(str).replace({"None": "", "nan": ""}) for k in PERF_TABLES}
    perf, rep = validate_perf_bundle(raw, demo=False)
    return perf


def fmt_status_line(row) -> str:
    return f"{row['status_label']} — {fmt_pct(row['score']) if row['score'] is not None else 'لا درجة'}"
