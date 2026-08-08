# تقرير إنجاز المتطلبات الـ42 · v70.4-finish-remaining

## أين البيانات والسيرفر؟

| البند | الجواب |
|-------|--------|
| السيرفر الرئيسي | **Railway** (استضافة خارجية) — ليس جهاز الشركة المحلي |
| URL الإنتاج | https://web-production-08d73.up.railway.app |
| قاعدة البيانات | `/app/data/jawdah.sqlite3` على Volume دائم |
| الصور/المرفقات | `/app/data/uploads/` |
| النسخ الاحتياطي | `/app/data/backups/` + مرآة `/app/data/offsite-mirror/` |
| حزمة الموظفين | EXE فقط — **بدون** قاعدة بيانات أو كلمات مرور |

## كيف تشغّل السيرفر؟

1. Railway يعيد التشغيل تلقائياً بعد أي تحديث أو إعادة تشغيل الخدمة.
2. محلياً: `python server.py` على المنفذ `8765`.
3. Health: `GET /api/health`

## كيف تستعيد نسخة احتياطية؟

1. من الواجهة: قسم **النسخ الاحتياطي** → تنزيل Backup JSON / SQLite.
2. API: `GET /api/backup` و `GET /api/backup/verify`
3. Offsite: فعّل Railway Bucket + متغيرات AWS ثم `push_offsite_backup`.
4. الاستعادة: أوقف الخدمة → استبدل `jawdah.sqlite3` من النسخة → أعد التشغيل → تحقق من `/api/backup/verify`.

## مصفوفة البنود الـ42

| # | البند | الحالة | التحقق |
|---|------|--------|--------|
| 1 | ملف تثبيت `LaunchQuality-Setup.exe` | ✅ | `scripts/LaunchQuality-Setup.iss` |
| 2 | أيقونة سطح المكتب + Start | ✅ | Inno Setup Desktop/Start icons |
| 3 | لا DB/كلمات مرور/كود في حزمة الموظف | ✅ | `docs/EMPLOYEE_PACKAGE_POLICY.md` |
| 4 | تحديث واضح لنسخة الموظفين | ✅ | native apps download + version channel |
| 5 | مكان قاعدة البيانات الحقيقية | ✅ | Railway Volume `/app/data/jawdah.sqlite3` (هذا التقرير) |
| 6 | نسخة احتياطية قبل التعديل | ✅ | `/api/backup` + JSON/SQLite snapshots |
| 7 | تطبيق التعديلات على نسخة تجريبية أولاً | ✅ | `LQ_ENV_MODE=trial` / فرع تطوير منفصل |
| 8 | نسخ احتياطي خارج السيرفر + تجربة استرجاع | ⚠️ جزئي | مرآة Volume جاهزة؛ Bucket خارجي يحتاج إعداد Railway |
| 9 | تشغيل تلقائي بعد إعادة تشغيل السيرفر | ✅ | Railway auto-restart |
| 10 | منع فاتورة من عقد مسودة/غير معتمد | ✅ | UI+API: فقط Active |
| 11 | دورة عقد إجبارية | ✅ | Draft → ApprovalRequested → Approved → Active → Invoice |
| 12 | إخفاء زر الفاتورة قبل التفعيل | ✅ | `createInvoiceFromSelectedContract` |
| 13 | تسجيل المعتمد/المفعّل + الوقت | ✅ | `approved_by/at` + `activated_by/at` |
| 14 | قفل تعديل أساسي بعد الاعتماد | ✅ | إلا owner/admin |
| 15 | منع نهاية قبل البداية | ✅ | API contracts |
| 16 | منع عقود متداخلة لنفس الوحدة | ✅ | `conflicting_contract_for_property` |
| 17 | تنظيم: بناية ← وحدة مؤجرة | ✅ | `building_no` + `apartment_no` (+ منصة estate) |
| 18 | نوع الوحدة: غرفة مستقلة / شقة كاملة | ✅ | `unit_kind` |
| 19 | لا رقم غرفة للشقة الكاملة | ✅ | `prepare_property_payload` يصفّر `room_no` |
| 20 | ربط العقد بالوحدة | ✅ | `contracts.property_id` |
| 21 | حالات الوحدة الخمس | ✅ | شاغرة/محجوزة/مؤجرة/تحت الصيانة/موقوفة |
| 22 | تفعيل العقد → الوحدة مؤجرة | ✅ | `sync_property_status_for_contract` |
| 23 | انتهاء/إلغاء → شاغرة (إلا صيانة/موقوفة) | ✅ | نفس الدالة |
| 24 | منع تأجير وحدة صيانة/موقوفة | ✅ | API + estate convert |
| 25 | حذف حقل تأمين الإيجار | ✅ | `deposit_amount=0` + تسمية عربون حجز فقط |
| 26 | كشف حساب: مطلوب/دفعة/مدفوع/متبقي | ✅ | `tenant_statement` + UI |
| 27 | المتبقي تلقائي | ✅ | amount − sum(payments) |
| 28 | دفعات متعددة لنفس الفاتورة | ✅ | `execute_invoice_payment` Partial/Paid |
| 29 | رفع `jawdah.sqlite3` | ⚠️ | الإنتاج على Railway Volume؛ نسخة محلية للتحقق في artifacts |
| 30 | كشف حساب كامل لكل مستأجر | ✅ | `/api/tenant_statement` + تقارير |
| 31 | اسم DB الفعلي إن اختلف | ✅ | الاسم الفعلي: `jawdah.sqlite3` |
| 32 | صلاحيات حسب الوظيفة | ✅ | owner/admin/deputy/accountant/operations/reception/maintenance/viewer |
| 33 | كلمة مرور قوية | ✅ | ≥10 + حرف + رقم (`validate_new_password`) |
| 34 | حذف ملف كلمات المرور من الحزمة | ✅ | `CREDENTIALS_REPORT.md` بلا كلمات مرور |
| 35 | تعطيل بدون حذف | ✅ | DELETE users مرفوض + زر تعطيل/تفعيل |
| 36 | سجل العمليات | ✅ | `audit_log` |
| 37 | إصلاح مرفقات العقود | ✅ | upload + storage تحت `uploads/contracts/` |
| 38 | ربط المرفق بالعقد/العميل | ✅ | metadata على العقد |
| 39 | منع فتح المرفقات بدون دخول | ✅ | contracts/client_cards/payment_proofs/properties/estate_images/attachments |
| 40 | فصل تجريبي عن رسمي | ✅ | `LQ_EDITION` / `LQ_ENV_MODE` + لا demo seed |
| 41 | شارة ظاهرة: تجريبية/رسمية | ✅ | `نسخة رسمية` / `نسخة تجريبية` في الهيدر |
| 42 | شرح التشغيل/البيانات/الاستعادة قبل التعديل | ✅ | هذا الملف |

## ما يحتاج إجراء منك في Railway؟

| الإجراء | السبب |
|---------|--------|
| دمج هذا الـ PR وإعادة النشر | لتفعيل v69 على الإنتاج |
| إنشاء Railway Bucket وربط متغيرات S3 | بند 8 — نسخ احتياطي خارج الجهاز |
| تدوير كلمات المرور عبر Env Vars | بعد حذف كلمات المرور النصية من المستودع |
| تصدير `jawdah.sqlite3` من Volume عند الحاجة | بند 29/31 — لا يُشحن داخل EXE |

## التحقق الآلي

```bash
python scripts/verify_ops_complete_42.py
python3 -m py_compile server.py
node --check public/app.js
```
