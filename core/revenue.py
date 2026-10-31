"""مؤشرات الإيرادات والفجوة، والسيناريوهات واختيار الفرص."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .opportunities import estimate
from .revenue_data import RevenueData


def compute_kpis(data: RevenueData) -> dict:
    """المستهدف، المحقق، الفجوة حتى اللقطة، نسبة التحقيق، والفجوة المتوقعة بنهاية السنة بعد الإيراد الأساسي.

    - المستهدف صفر: نسبة التحقيق غير قابلة للحساب (None) ولا توجد فجوة.
    - لا تُعرض فجوة سالبة؛ الزيادة تظهر كفائض.
    """
    s = data.settings
    target = float(s.annual_target_sar)
    realized = float(data.sources["realized_to_date_sar"].sum())
    baseline = float(data.sources["expected_remaining_sar"].sum())
    projected = realized + baseline
    return {
        "target": target,
        "realized": realized,
        "gap_to_date": max(0.0, target - realized),
        "surplus_to_date": max(0.0, realized - target),
        "attainment_pct": (realized / target * 100) if target > 0 else None,
        "baseline_remaining": baseline,
        "projected_year_end": projected,
        "projected_gap": max(0.0, target - projected),
        "projected_surplus": max(0.0, projected - target),
        "projected_attainment_pct": (projected / target * 100) if target > 0 else None,
        "remaining_days": s.remaining_days,
        "days_in_year": s.days_in_year,
    }


def sources_table(data: RevenueData) -> pd.DataFrame:
    df = data.sources.copy()
    df["attainment_pct"] = df.apply(lambda r: r["realized_to_date_sar"] / r["annual_target_sar"] * 100 if r["annual_target_sar"] > 0 else None, axis=1)
    df["projected_sar"] = df["realized_to_date_sar"] + df["expected_remaining_sar"]
    df["projected_gap_sar"] = (df["annual_target_sar"] - df["projected_sar"]).clip(lower=0)
    return df


@dataclass
class SelectionResult:
    kept: list
    dropped: list = field(default_factory=list)  # [(opp_id, reason)]


def resolve_selection(opps: pd.DataFrame, selected_ids) -> SelectionResult:
    """يمنع التكرار والتعارض:
    - المعرف المكرر يُحتسب مرة واحدة.
    - المعرفات غير الموجودة تُتجاهل مع ذكرها.
    - فرصتان في مجموعة التعارض نفسها (الأصل نفسه/المدين نفسه): تُبقى الأعلى أولوية فقط.
    """
    seen, ordered, dropped = set(), [], []
    valid = set(opps["opp_id"]) if not opps.empty else set()
    for oid in selected_ids or []:
        if oid in seen:
            continue
        seen.add(oid)
        if oid not in valid:
            dropped.append((oid, "معرف غير موجود في الفرص الحالية"))
            continue
        ordered.append(oid)
    if not ordered:
        return SelectionResult([], dropped)
    sub = opps[opps["opp_id"].isin(ordered)].sort_values(["priority_score", "in_year"], ascending=False)
    kept, groups = [], {}
    for _, row in sub.iterrows():
        g = row["conflict_group"]
        if g in groups:
            dropped.append((row["opp_id"], f"تتعارض مع {groups[g]} على المرجع نفسه ({g.split(':', 1)[1]}) — احتُسبت الأعلى أولوية فقط"))
            continue
        groups[g] = row["opp_id"]
        kept.append(row["opp_id"])
    return SelectionResult(kept, dropped)


def scenario_result(opps: pd.DataFrame, selected_ids, multiplier: float, kpis: dict, basis: str) -> dict:
    """إجمالي الإيراد الإضافي خلال السنة والفجوة المتبقية والفائض لسيناريو واحد."""
    sel = resolve_selection(opps, selected_ids)
    rows = []
    for oid in sel.kept:
        o = opps.loc[opps["opp_id"] == oid].iloc[0]
        e = estimate(o, multiplier)
        counts_in_gap = o["nature"] == "recurring" or basis == "cash"
        rows.append({
            "opp_id": oid,
            "title": o["title"],
            "opp_type": o["opp_type"],
            "nature": o["nature"],
            "base_in_year": float(o["in_year"]),
            "in_year": e["in_year"],
            "annual": e["annual"],
            "one_time_total": e["one_time_total"],
            "capped": e["capped"],
            "counts_in_gap": counts_in_gap,
        })
    det = pd.DataFrame(rows, columns=["opp_id", "title", "opp_type", "nature", "base_in_year", "in_year", "annual", "one_time_total", "capped", "counts_in_gap"])
    recurring = float(det.loc[det["nature"] == "recurring", "in_year"].sum()) if not det.empty else 0.0
    one_time = float(det.loc[det["nature"] == "one_time", "in_year"].sum()) if not det.empty else 0.0
    contribution = recurring + (one_time if basis == "cash" else 0.0)
    projected_with = kpis["projected_year_end"] + contribution
    target = kpis["target"]
    return {
        "selection": sel,
        "detail": det,
        "recurring_in_year": recurring,
        "one_time_in_year": one_time,
        "contribution": contribution,
        "excluded_cash_only": one_time if basis != "cash" else 0.0,
        "annual_recurring_potential": float(det["annual"].sum()) if not det.empty else 0.0,
        "projected_with_opps": projected_with,
        "remaining_gap": max(0.0, target - projected_with),
        "surplus": max(0.0, projected_with - target),
        "gap_closed_pct": (min(contribution, kpis["projected_gap"]) / kpis["projected_gap"] * 100) if kpis["projected_gap"] > 0 else None,
    }


def auto_select(opps: pd.DataFrame, kpis: dict, multiplier: float, basis: str) -> list:
    """اختيار تلقائي: الأعلى أولوية أولًا، مع تخطي المتعارض وما ليس له أثر هذا العام،
    والتوقف عند تغطية الفجوة المتوقعة بنهاية السنة (أو انتهاء الفرص)."""
    if opps.empty:
        return []
    need = kpis["projected_gap"]
    chosen, groups, acc = [], set(), 0.0
    for _, o in opps.sort_values(["priority_score", "in_year"], ascending=False).iterrows():
        if need <= 0 or acc >= need:
            break
        if o["conflict_group"] in groups:
            continue
        if o["nature"] == "one_time" and basis != "cash":
            continue
        val = estimate(o, multiplier)["in_year"]
        if val <= 0:
            continue
        chosen.append(o["opp_id"])
        groups.add(o["conflict_group"])
        acc += val
    return chosen
