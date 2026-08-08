# مسار PostgreSQL — المرحلة 1 (ظلّي)

## الهدف
تهيئة PostgreSQL للتحقق فقط دون تغيير محرك التشغيل الأساسي.

- **الأساسي الآن:** SQLite
- **الظل:** نسخة تحقق على PostgreSQL عبر `LQ_DATABASE_URL`

## أين تجده؟
القائمة → **التوسع المؤسسي** → بطاقة «مسار PostgreSQL».

## واجهات API (تتطلب صلاحية admin)
| الطريقة | المسار | الوظيفة |
|---------|--------|---------|
| GET | `/api/database/status` | حالة المنصة + فحص سريع |
| GET | `/api/database/postgres_probe` | اختبار الاتصال |
| POST | `/api/database/migrate_preview` | معاينة بدون كتابة |
| POST | `/api/database/migrate_shadow` | نسخ ظلّي (`{"confirm":"shadow"}`) |
| GET | `/api/database/verify_shadow` | مقارنة أعداد الصفوف |

## تفعيل على Railway
1. أضف خدمة PostgreSQL (أو استخدم قاعدة موجودة).
2. عيّن المتغير:
   - `LQ_DATABASE_URL` = رابط الاتصال  
   - أو `DATABASE_URL` (يُقبل أيضاً)
3. أعد النشر بعد إضافة `psycopg` في `requirements.txt`.
4. من الواجهة: **فحص الاتصال → معاينة → نسخ ظلّي → تحقق العدّ**.

## ما لا يفعله هذا الإصدار
- لا يحوّل القراءة/الكتابة اليومية إلى Postgres.
- لا يفعّل dual-write.
- المرحلة التالية: محوّل لهجة SQL + كتابة مزدوجة ثم قطع تدريجي.
