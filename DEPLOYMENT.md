# النشر برابط مباشر عبر GitHub وStreamlit Community Cloud

الهدف: رابط يفتح من الجوال والكمبيوتر دون Terminal ودون إبقاء جهازك مفتوحًا. النسخة المنشورة تعمل بالبيانات التجريبية فقط (وضع العرض مفعّل افتراضيًا ويرفض أي بيانات موسومة `real`).

> **الحالة:** لم يُنشر التطبيق بعد. بيئة البناء لا تملك صلاحية على حساب GitHub الخاص بك، فالخطوات أدناه تحتاج حسابك (نحو 10 دقائق).

## 1) رفع المشروع إلى GitHub (دون Terminal)

1. ادخل إلى github.com وأنشئ حسابًا إن لم يكن لديك.
2. اضغط **New repository** ← الاسم مثل `hail-revenue-performance` ← اختر **Public** ← **Create repository**.
3. في صفحة المستودع الفارغ اختر **uploading an existing file**.
4. فك ضغط ملف ZIP على جهازك، ثم اسحب **محتويات** مجلد `hail-platform` (وليس المجلد نفسه) إلى الصفحة.
   - تأكد أن `app.py` و`requirements.txt` ومجلدات `core` و`ui` و`data` و`static` و`.streamlit` في جذر المستودع.
   - مجلد `.streamlit` مخفي في Finder؛ اضغط `Cmd + Shift + .` لإظهاره قبل السحب. بدونه لن يُحمّل الخط العربي والسمة.
5. اضغط **Commit changes**.

**بديل عبر Terminal:**

```bash
cd hail-platform
git init && git add . && git commit -m "Prototype v1.0.0"
git branch -M main
git remote add origin https://github.com/<اسم_المستخدم>/hail-revenue-performance.git
git push -u origin main
```

## 2) النشر على Streamlit Community Cloud

1. ادخل إلى share.streamlit.io وسجّل الدخول بحساب GitHub، واسمح لـ Streamlit بالوصول إلى المستودعات.
2. اضغط **Create app** ← **Deploy a public app from GitHub**.
3. اختر المستودع `hail-revenue-performance`، الفرع `main`، والملف الرئيسي `app.py`.
4. اختر رابطًا مميزًا (App URL) مثل `hail-revenue-prototype`.
5. افتح **Advanced settings** واختر **Python 3.13** (أو 3.12). لا حاجة لأي أسرار (Secrets).
6. اضغط **Deploy** وانتظر اكتمال تثبيت المكتبات (بضع دقائق في المرة الأولى).

بعد النجاح يظهر رابط بصيغة `https://<الاسم>.streamlit.app`. افتحه من الجوال للتأكد.

## 3) بعد النشر

- **الشعار:** مضمّن في `assets/logo/hail_logo.png`. لاستبداله ارفع ملفًا بالاسم نفسه (Add file ← Upload files) فيُعاد النشر تلقائيًا.
- **التحديثات:** أي تعديل يُرفع إلى الفرع `main` يُعاد نشره تلقائيًا.
- **الحفظ:** البيانات المدخلة في النسخة المنشورة تبقى في جلسة المتصفح فقط. استخدم «تنزيل نسخة احتياطية» و«استعادة».
- **السكون:** قد يدخل التطبيق المجاني في وضع السكون بعد فترة دون استخدام؛ يكفي فتح الرابط والضغط على زر الإيقاظ.
- **الخصوصية:** لا ترفع بيانات حقيقية للأمانة إلى مستودع عام أو نسخة منشورة عامة. للتشغيل الداخلي على بيانات حقيقية: شغّل محليًا أو على خادم داخلي مع `HAIL_DEMO_MODE=0`.

## مشكلات شائعة

| العرض | الحل |
|---|---|
| الخط ليس عربيًا حديثًا أو الألوان افتراضية | مجلد `.streamlit` أو `static` لم يُرفع إلى جذر المستودع |
| خطأ في تثبيت المكتبات | تأكد من اختيار Python 3.13 أو 3.12 في Advanced settings |
| `ModuleNotFoundError: core` | الملف الرئيسي يجب أن يكون `app.py` في جذر المستودع وليس داخل مجلد فرعي |
