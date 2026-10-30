"""فرص الإيرادات: نتائج محرك التحليل مع الأدلة وطريقة الحساب والافتراضات والموافقات."""
from __future__ import annotations

import streamlit as st

from core.formatting import esc, fmt_int, fmt_sar
from core.opportunities import EASE_LABELS, RISK_LABELS, TYPE_LABELS

from ..components import calc_block, html, kpi, kpi_grid, kpi_money, note, rich, section, table, tag
from ..state import opportunities, ss


def _weights_editor():
    with st.expander("معادلة ترتيب الأولوية والأوزان (قابلة للتعديل)", expanded=False):
        html('<div class="note info">'
             "<b>درجة الأولوية</b> = (و<sub>1</sub> × مساهمة السنة المعيارية + و<sub>2</sub> × السهولة المعيارية + و<sub>3</sub> × عكس المخاطر) ÷ (و<sub>1</sub>+و<sub>2</sub>+و<sub>3</sub>)"
             "<ul><li>مساهمة السنة المعيارية = مساهمة الفرصة حتى نهاية السنة ÷ أعلى مساهمة بين الفرص × 100</li>"
             "<li>السهولة المعيارية = (السهولة − 1) ÷ 4 × 100، وعكس المخاطر = (5 − المخاطر) ÷ 4 × 100 (المقياسان من 1 إلى 5)</li>"
             "<li>الدرجة نسبية للمقارنة بين الفرص الحالية فقط، <b>وليست احتمال نجاح</b>.</li></ul></div>")
        w = ss.priority_weights
        c1, c2, c3 = st.columns(3)
        a = c1.number_input("وزن مساهمة السنة %", 0, 100, int(w["contribution"]), 5, key="w_contrib")
        b = c2.number_input("وزن سهولة التنفيذ %", 0, 100, int(w["ease"]), 5, key="w_ease")
        c = c3.number_input("وزن انخفاض المخاطر %", 0, 100, int(w["risk"]), 5, key="w_risk")
        if a + b + c == 0:
            st.error("لا يمكن أن تكون كل الأوزان صفرًا — أُبقيت الأوزان السابقة.")
        else:
            if (a, b, c) != (w["contribution"], w["ease"], w["risk"]):
                ss.priority_weights = {"contribution": a, "ease": b, "risk": c}
                st.rerun()
            if a + b + c != 100:
                st.caption(f"مجموع الأوزان {a + b + c}% — تُطبّع تلقائيًا بالقسمة على المجموع.")


def render():
    _weights_editor()
    opps, excluded = opportunities()
    s = ss.rev_data.settings
    if opps.empty:
        note("<b>لم يكتشف المحرك أي فرصة</b> وفق البيانات والقواعد الحالية. راجع قائمة المستبعد أدناه، أو حدّث بيانات الأصول والعقود والمستحقات.", "warn")
    rec = opps[opps["nature"] == "recurring"] if not opps.empty else opps
    one = opps[opps["nature"] == "one_time"] if not opps.empty else opps
    kpi_grid([
        kpi("الفرص المكتشفة", f"{len(opps)}", f"تأجير {int((opps['opp_type'] == 'lease').sum()) if len(opps) else 0} · تجديد {int((opps['opp_type'] == 'renewal').sum()) if len(opps) else 0} · تحصيل {int((opps['opp_type'] == 'collection').sum()) if len(opps) else 0}", "primary"),
        kpi_money("الإيراد السنوي المحتمل (سنة تشغيل كاملة)", float(rec.groupby("conflict_group")["annual_potential"].max().sum()) if len(rec) else 0.0, "ok", extra="متكرر — أعلى بديل واحد لكل أصل (لا جمع للمتعارض)"),
        kpi_money("الممكن من الإيراد المتكرر حتى نهاية السنة", float(rec.groupby("conflict_group")["in_year"].max().sum()) if len(rec) else 0.0, "gold", extra="بعد مهلة التنفيذ وتواريخ التجديد"),
        kpi_money("تحصيل لمرة واحدة ممكن حتى نهاية السنة", float(one["in_year"].sum()) if len(one) else 0.0, "neutral", extra="بعد طرح التحصيل المتوقع أصلًا"),
        kpi("عناصر مستبعدة", f"{len(excluded)}", "أصول مقيدة أو غير مناسبة، عقود غير قابلة للمراجعة، ومطالبات متنازع عليها", "alert"),
    ])

    if opps.empty:
        _excluded(excluded)
        _method_note()
        return
    section("الفرص مرتبة حسب درجة الأولوية", "المساهمة حتى نهاية السنة هي ما يدخل في سد فجوة هذه السنة")
    types = st.multiselect("تصفية حسب نوع الفرصة", list(TYPE_LABELS), default=list(TYPE_LABELS), format_func=lambda x: TYPE_LABELS[x], key="opp_types")
    view = opps[opps["opp_type"].isin(types)]
    sel = set(ss.selection)
    rows, rc = [], []
    for o in view.itertuples():
        rows.append([
            f"{o.rank}", f"<b>{esc(o.opp_id)}</b><div class='muted'>{esc(o.ref_display)}</div>",
            f"{esc(o.title)}<div class='muted'>{esc(o.type_label)}</div>",
            tag(o.nature_label, "gold" if o.nature == "one_time" else ""),
            fmt_int(o.in_year),
            fmt_int(o.annual_potential) if o.nature == "recurring" else f"{fmt_int(o.one_time_total)}<div class='muted'>إجمالي الحملة</div>",
            f"<span class='ltr'>{o.effective_date.isoformat()}</span><div class='muted'>{o.in_year_days} يومًا ضمن السنة</div>",
            f"{EASE_LABELS[o.ease]}<div class='muted'>مخاطر {RISK_LABELS[o.risk]}</div>",
            f"<b>{o.priority_score:.1f}</b>",
        ])
        rc.append("sel" if o.opp_id in sel else "")
    html(table([("#", "c"), ("المعرف والمرجع", ""), ("الفرصة", ""), ("الطبيعة", ""), ("حتى نهاية السنة (ريال)", "num"), ("سنوي محتمل (ريال)", "num"),
                ("بدء الأثر", ""), ("السهولة / المخاطر", ""), ("الأولوية", "c")], rows, rc))
    st.caption("الصفوف المظللة = مختارة حاليًا في صفحة السيناريوهات. فرص الأصل الواحد بدائل متعارضة ولا تُجمع معًا.")

    section("تفاصيل فرصة")
    if view.empty:
        note("لا توجد فرص ضمن الأنواع المختارة.", "info")
        _excluded(excluded)
        _method_note()
        return
    oid = st.selectbox("اختر فرصة لعرض الأدلة والحساب", list(view["opp_id"]), format_func=lambda x: f"{x} — {view.set_index('opp_id').at[x, 'title']}", key="opp_detail")
    o = opps.set_index("opp_id").loc[oid]
    ev = "".join(f"<dt>{esc(a)}</dt><dd>{rich(b)}</dd>" for a, b in o["evidence"])
    ass = "".join(f"<li>{rich(a)}</li>" for a in o["assumptions"])
    apr = "".join(f"<li>{esc(a)}</li>" for a in o["approvals"])
    in_gap = "يُحتسب في سد الفجوة" if (o["nature"] == "recurring" or s.financial_basis == "cash") else "لا يُحتسب في سد الفجوة على أساس الاستحقاق (أثر نقدي فقط)"
    html(f"""<div class="opp"><h4>{esc(oid)} — {esc(o['title'])}</h4>
<div class="meta">{tag(o['type_label'])}{tag(o['nature_label'], 'gold' if o['nature'] == 'one_time' else '')}{tag('الأولوية ' + format(o['priority_score'], '.1f'), 'gray')}{tag('السهولة: ' + EASE_LABELS[o['ease']], 'gray')}{tag('المخاطر: ' + RISK_LABELS[o['risk']], 'gray')}{tag(in_gap, 'gray')}</div>
<p style="margin:0 0 6px"><b>سبب الاقتراح:</b> {rich(o['reason'])}</p>
<div class="grid2">
 <div><h5>الأدلة والقيم المستخدمة من البيانات</h5><dl>{ev}</dl></div>
 <div><h5>طريقة حساب الإيراد</h5>{calc_block(o['method'])}
  <dl style="margin-top:10px"><dt>حتى نهاية السنة</dt><dd><b>{esc(fmt_sar(o['in_year']))}</b></dd>
  <dt>{'سنة تشغيل كاملة' if o['nature'] == 'recurring' else 'إجمالي الحملة (لمرة واحدة)'}</dt><dd>{esc(fmt_sar(o['annual_potential'] if o['nature'] == 'recurring' else o['one_time_total']))}</dd>
  <dt>مدة التنفيذ المتوقعة</dt><dd>{o['lead_days']} يومًا — بدء الأثر <bdi dir="ltr">{o['effective_date'].isoformat()}</bdi></dd>
  <dt>السقف في السيناريوهات</dt><dd>{esc(o['cap_note'])}</dd>
  <dt>مجموعة التعارض</dt><dd>{esc(o['conflict_group'])}</dd></dl></div>
</div>
<div class="grid2"><div><h5>الافتراضات</h5><ul>{ass}</ul></div><div><h5>المراجعات والموافقات المطلوبة</h5><ul>{apr}</ul></div></div>
<div class="disclaimer">هذا اقتراح تحليلي وليس موافقة تنظيمية أو إذنًا بالتنفيذ. التقدير مبني على بيانات تجريبية وافتراضات قابلة للتعديل، ويحتاج تحقق الجهات المختصة قبل أي إجراء.</div>
</div>""")
    _excluded(excluded)
    _method_note()


def _method_note():
    """ملاحظة المنهجية في آخر الصفحة بدل أعلاها."""
    note("<b>لا يوجد نموذج تعلم آلة مدرب في هذا الإصدار.</b> الفرص مستخرجة بقواعد تحليلية قابلة للتفسير من بيانات الأصول والعقود والمستحقات والمراجع السوقية، "
         "ولكل فرصة أدلتها وطريقة حسابها. لم تُدرَّب نماذج على البيانات التجريبية لأن دقتها لن تدل على صلاحية حقيقية. الاقتراح تحليلي وليس موافقة تنظيمية أو إذنًا بالتنفيذ، "
         "والإيراد المعروض قبل خصم تكاليف التنفيذ والتشغيل (إيراد وليس ربحًا).", "info")


def _excluded(excluded):
    with st.expander(f"ما الذي استُبعد ولماذا ({len(excluded)})", expanded=False):
        if excluded.empty:
            st.write("لا توجد عناصر مستبعدة.")
        else:
            html(table([("المرجع", ""), ("النوع", ""), ("سبب الاستبعاد", "")], [[esc(a), esc(b), esc(c)] for a, b, c in excluded.itertuples(index=False)]))
