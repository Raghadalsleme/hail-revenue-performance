# نتائج الاختبارات الفعلية

- تاريخ التشغيل: 2026-10-30 14:23
- البيئة: Python 3.13.18 على Linux، Streamlit 1.66.1، Chromium (Playwright)
- البيانات: Synthetic Data — بيانات تجريبية لا تمثل أرقام أمانة منطقة حائل

## 1) اختبارات pytest

**الخلاصة:** `93 passed in 12.43s`

| الملف | ما يغطيه | العدد |
|---|---|---|
| `test_exports.py` | PDF عربي (الخط المضمّن، اتجاه النص وانعكاس الأقواس)، Excel الإيرادات والأداء (الأوراق، RTL، تمييز المختارة، الأوزان والحدود)، القوالب | 5 |
| `test_imports.py` | قبول الصحيح ورفض الأعمدة المفقودة والمكررات والمراجع والتواريخ والسالب وغير المحدود والنسب خارج الحدود وخلط الحقيقي بالتجريبي دون تغيير البيانات الحالية، النسخ الاحتياطي، SQLite | 24 |
| `test_performance.py` | تحقيق المؤشر وسقف 100%، حدود 70 و90، تقريب الدرجة، الأوزان، المفقود مقابل الصفر، مقارنة الشهر السابق، تصفية الإدارة العامة، تغيير الأسماء مع حفظ التاريخ، الإدخال الشهري | 22 |
| `test_revenue.py` | الفجوة ونسبة الإنجاز والفائض، المستهدف صفر، تقديرات التأجير والتجديد والتحصيل، أثر المهلة والفترة المتبقية ونهاية السنة، الاستبعادات، تغير النتائج بتغير المدخلات، عدم وجود فرص | 22 |
| `test_scenarios.py` | منع تكرار الفرص وتعارضها، السيناريوهات والسقوف، أساس الاستحقاق، الاختيار التلقائي، الفجوة المتبقية والفائض، عدم وجود فرص | 10 |
| `test_ui.py` | AppTest: عرض كل الصفحات، أزرار السيناريوهات، معاملات الحساسية، تصفية الإدارة ورفض الأوزان غير الصحيحة، تغيير المستهدف، أوزان الأولوية، نموذج الإدخال الشهري ورفض المستهدف الصفري، تعديل اسم قسم | 10 |

<details><summary>القائمة الكاملة</summary>

```
tests/test_exports.py::test_revenue_pdf_valid PASSED
tests/test_exports.py::test_arabic_visual_order_and_mirroring PASSED
tests/test_exports.py::test_revenue_excel_contents PASSED
tests/test_exports.py::test_perf_exports PASSED
tests/test_exports.py::test_templates_open PASSED
tests/test_imports.py::test_valid_bundle_accepted PASSED
tests/test_imports.py::test_missing_required_column_rejected PASSED
tests/test_imports.py::test_duplicate_ids_rejected PASSED
tests/test_imports.py::test_broken_reference_rejected PASSED
tests/test_imports.py::test_bad_dates_rejected PASSED
tests/test_imports.py::test_negative_and_infinite_values_rejected PASSED
tests/test_imports.py::test_ratio_out_of_bounds_rejected PASSED
tests/test_imports.py::test_paid_more_than_due_rejected PASSED
tests/test_imports.py::test_mixed_real_and_synthetic_rejected PASSED
tests/test_imports.py::test_demo_mode_rejects_real_data PASSED
tests/test_imports.py::test_revenue_excel_roundtrip PASSED
tests/test_imports.py::test_perf_merge_valid_upload_replaces_only_uploaded_dept_months PASSED
tests/test_imports.py::test_perf_invalid_uploads_rejected_without_changes[rows0-\u0645\u0643\u0631\u0631\u0629] PASSED
tests/test_imports.py::test_perf_invalid_uploads_rejected_without_changes[rows1-\u062e\u0627\u0631\u062c \u0627\u0644\u062d\u062f\u0648\u062f] PASSED
tests/test_imports.py::test_perf_invalid_uploads_rejected_without_changes[rows2-\u0627\u0644\u062d\u062f \u0627\u0644\u0623\u062f\u0646\u0649] PASSED
tests/test_imports.py::test_perf_invalid_uploads_rejected_without_changes[rows3-\u0645\u0631\u0627\u062c\u0639 \u063a\u064a\u0631 \u0645\u0648\u062c\u0648\u062f\u0629] PASSED
tests/test_imports.py::test_perf_invalid_uploads_rejected_without_changes[rows4-\u0635\u064a\u063a\u0629 \u0634\u0647\u0631] PASSED
tests/test_imports.py::test_perf_invalid_uploads_rejected_without_changes[rows5-\u0645\u0631\u0627\u062c\u0639 \u063a\u064a\u0631 \u0645\u0648\u062c\u0648\u062f\u0629] PASSED
tests/test_imports.py::test_perf_invalid_uploads_rejected_without_changes[rows6-\u0633\u0627\u0644\u0628\u0629] PASSED
tests/test_imports.py::test_perf_invalid_uploads_rejected_without_changes[rows7-\u062e\u0644\u0637] PASSED
tests/test_imports.py::test_perf_missing_actual_allowed_and_kept_blank PASSED
tests/test_imports.py::test_perf_csv_single_file_and_missing_columns PASSED
tests/test_imports.py::test_perf_backup_roundtrip PASSED
tests/test_imports.py::test_sqlite_local_persistence_roundtrip PASSED
tests/test_performance.py::test_kpi_achievement_rules PASSED
tests/test_performance.py::test_classification_boundaries[90.0-good] PASSED
tests/test_performance.py::test_classification_boundaries[89.99-medium] PASSED
tests/test_performance.py::test_classification_boundaries[70.0-medium] PASSED
tests/test_performance.py::test_classification_boundaries[69.99-intervene] PASSED
tests/test_performance.py::test_classification_boundaries[100-good] PASSED
tests/test_performance.py::test_classification_boundaries[0-intervene] PASSED
tests/test_performance.py::test_classification_boundaries[None-incomplete] PASSED
tests/test_performance.py::test_weighted_score_and_cap_prevents_compensation PASSED
tests/test_performance.py::test_float_artifacts_rounded_before_classification PASSED
tests/test_performance.py::test_missing_value_is_not_zero PASSED
tests/test_performance.py::test_department_without_any_data_is_grey_not_red PASSED
tests/test_performance.py::test_weights_change_score PASSED
tests/test_performance.py::test_settings_validation PASSED
tests/test_performance.py::test_custom_thresholds_change_status PASSED
tests/test_performance.py::test_previous_calendar_month_comparison PASSED
tests/test_performance.py::test_incomplete_previous_month_gives_no_comparison PASSED
tests/test_performance.py::test_general_department_filter PASSED
tests/test_performance.py::test_trend_keeps_missing_month_as_gap PASSED
tests/test_performance.py::test_rename_keeps_history_and_ids PASSED
tests/test_performance.py::test_add_department_gets_new_stable_id PASSED
tests/test_performance.py::test_upsert_month_blank_is_not_zero_and_only_month_replaced PASSED
tests/test_revenue.py::test_gap_and_attainment_synthetic PASSED
tests/test_revenue.py::test_surplus_when_realized_exceeds_target PASSED
tests/test_revenue.py::test_zero_target_has_no_attainment_and_no_gap PASSED
tests/test_revenue.py::test_remaining_days_and_year_end PASSED
tests/test_revenue.py::test_lease_estimate_subtracts_current_revenue_and_respects_lead_time PASSED
tests/test_revenue.py::test_lease_land_with_grace_period_has_no_in_year_effect PASSED
tests/test_revenue.py::test_earlier_snapshot_increases_in_year_contribution PASSED
tests/test_revenue.py::test_snapshot_at_year_end_gives_zero_in_year PASSED
tests/test_revenue.py::test_restricted_residential_and_missing_benchmark_are_excluded PASSED
tests/test_revenue.py::test_billboard_alternative_conflicts_with_land_lease PASSED
tests/test_revenue.py::test_renewal_uplift_counts_only_after_renewal_date PASSED
tests/test_revenue.py::test_renewal_contractual_cap_applies PASSED
tests/test_revenue.py::test_renewal_next_year_has_zero_in_year_but_annual_value PASSED
tests/test_revenue.py::test_renewal_review_lead_delays_effect_when_renewal_is_too_soon PASSED
tests/test_revenue.py::test_renewal_exclusions PASSED
tests/test_revenue.py::test_collection_subtracts_paid_and_baseline_and_applies_time_factor PASSED
tests/test_revenue.py::test_collection_cap_is_outstanding_balance PASSED
tests/test_revenue.py::test_collection_exclusions_disputed_scheduled_young_and_fully_paid PASSED
tests/test_revenue.py::test_collection_small_debtors_are_pooled PASSED
tests/test_revenue.py::test_changing_recovery_rate_changes_result PASSED
tests/test_revenue.py::test_no_opportunities_dataset PASSED
tests/test_revenue.py::test_synthetic_engine_outputs_are_evidence_backed PASSED
tests/test_scenarios.py::test_duplicate_ids_counted_once PASSED
tests/test_scenarios.py::test_conflicting_alternatives_on_same_asset_not_summed PASSED
tests/test_scenarios.py::test_unknown_ids_ignored_with_reason PASSED
tests/test_scenarios.py::test_scenarios_ordered_and_lease_capped_at_full_occupancy PASSED
tests/test_scenarios.py::test_accrual_basis_excludes_collection_from_gap PASSED
tests/test_scenarios.py::test_remaining_gap_and_surplus PASSED
tests/test_scenarios.py::test_auto_select_stops_when_gap_covered_and_skips_conflicts PASSED
tests/test_scenarios.py::test_no_opportunities_shows_full_gap PASSED
tests/test_scenarios.py::test_changing_target_changes_gap_and_result PASSED
tests/test_scenarios.py::test_synthetic_default_scenario_does_not_cover_gap PASSED
tests/test_ui.py::test_all_pages_render PASSED
tests/test_ui.py::test_revenue_page_shows_gap PASSED
tests/test_ui.py::test_scenario_buttons_change_selection PASSED
tests/test_ui.py::test_multiplier_change_updates_state PASSED
tests/test_ui.py::test_performance_filter_and_settings PASSED
tests/test_ui.py::test_revenue_settings_change_target PASSED
tests/test_ui.py::test_priority_weights_reorder PASSED
tests/test_ui.py::test_month_entry_form_saves_and_blank_stays_missing PASSED
tests/test_ui.py::test_month_entry_rejects_zero_target PASSED
tests/test_ui.py::test_rename_department_from_ui_keeps_id PASSED
```

</details>

## 2) فحص شامل في متصفح حقيقي على التطبيق العامل (`scripts/e2e_check.py`)

```
PASS تحميل الصفحة الرئيسية دون أخطاء 
PASS التنقل: لوحة الإيرادات المحدد=لوحة الإيرادات
PASS التنقل: فرص الإيرادات المحدد=فرص الإيرادات
PASS التنقل: السيناريوهات المحدد=السيناريوهات
PASS التنقل: أداء الإدارات المحدد=أداء الإدارات
PASS التنقل: إدخال بيانات الأداء المحدد=إدخال بيانات الأداء
PASS التنقل: البيانات والإعدادات المحدد=البيانات والإعدادات
PASS التنقل: التقارير المحدد=التقارير
PASS التنقل: المنهجية المحدد=المنهجية
PASS زر إلغاء الاختيارات 
PASS زر الاختيار التلقائي 
PASS نموذج افتراضات المحرك 
PASS رفض ملف أداء مكرر دون تغيير البيانات 
PASS تنزيل PDF الإيرادات 110,706 بايت
PASS تنزيل Excel الإيرادات 42,895 بايت
PASS تنزيل Excel الأداء 10,990 بايت
PASS لا أخطاء بعد كل التفاعلات 

17/17 نجحت
```

## 3) الفحص البصري

التُقطت صور من التطبيق العامل عبر Chromium بعرض نافذة عادي 1366×768 (وصفحات كاملة) وبعرض جوال 390×844، وفُحصت بصريًا: الترويسة، شريط التنقل، البطاقات، الرسوم، الجداول، ونموذج الإدخال. قيس أيضًا التمرير الأفقي غير المرغوب (يجب أن يكون صفرًا):

```
desktop revenue horizontal-overflow-px: 0 page-height: 2337
desktop opportunities horizontal-overflow-px: 0 page-height: 4130
desktop scenarios horizontal-overflow-px: 0 page-height: 2439
desktop performance horizontal-overflow-px: 0 page-height: 3100
desktop perf_entry horizontal-overflow-px: 0 page-height: 1688
desktop data horizontal-overflow-px: 0 page-height: 1254
desktop reports horizontal-overflow-px: 0 page-height: 827
desktop method horizontal-overflow-px: 0 page-height: 2204
desktop page errors: []
mobile revenue horizontal-overflow-px: 0 page-height: 4498
mobile opportunities horizontal-overflow-px: 0 page-height: 11031
mobile performance horizontal-overflow-px: 0 page-height: 6123
mobile scenarios horizontal-overflow-px: 0 page-height: 6639
mobile page errors: []
```

### مشكلات اكتُشفت أثناء الفحص وأُصلحت

- شريط التنقل كان يعرض دوائر الراديو الافتراضية بسبب تغير بنية Streamlit — أُعيد تنسيقه كتبويبات.
- تمرير أفقي بـ359 بكسل على الجوال سببه حقول الراديو المخفية — حُصر داخل شريط التنقل.
- خطأ في صفحة البيانات بسبب تعارض مفتاح نموذج مع مفتاح حالة الجلسة — أُعيدت تسمية النماذج (لم يكتشفه AppTest واكتشفه فحص المتصفح).
- المعادلات الرقمية كانت تنعكس داخل النص العربي — تُعرض الآن من اليسار لليمين، والتواريخ والنسب معزولة الاتجاه.
- شبكة إدخال البيانات (Glide) كانت تُرسم معكوسة بينما يُحتسب النقر من اليسار فيُحرَّر عمود خاطئ — استُبدلت بحقول رقمية تدعم RTL، والحقل الفارغ يبقى «غير مدخل».
- رسم الشلال كان بمحور مقتطع — استُبدل بأشرطة تبدأ من الصفر.
- الأقواس في PDF كانت معكوسة مع مكتبة bidi الحديثة — استُخدم التنفيذ الذي يعكسها بشكل صحيح، مع اختبار.

### تحديث بعد ملاحظات المستخدم
- أُزيل الشريط الأصفر العلوي وشارة «نموذج أولي» من الترويسة، ونُقلت حالة النظام ووسم البيانات التجريبية وملاحظة عدم وجود نموذج تعلم آلة إلى تذييل كل صفحة، وإلى تذييل تقارير PDF وآخرها.
- أُضيف الشعار المرفق في الترويسة وتقارير PDF. أُعيد تشغيل كل الفحوص بعد التعديل: 93 اختبار pytest و17/17 في المتصفح، دون تمرير أفقي ودون أخطاء.

## ما لم يُختبر

- النشر الفعلي على Streamlit Community Cloud (لا توجد صلاحية على حساب GitHub من بيئة البناء).
- التشغيل على macOS فعليًا (اختُبر على Linux بنفس إصدارات المكتبات؛ `run_mac.command` لم يُشغّل على Mac).
- متصفح Safari والأجهزة اللوحية؛ الفحص البصري تم على Chromium فقط.
- استيراد ملفات Excel منشأة يدويًا ببرامج غير Excel (مثل Numbers).
