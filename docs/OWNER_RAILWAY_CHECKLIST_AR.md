# قائمة المالك — إعداد Railway المتبقي

الكود جاهز. البنود التالية تتم من لوحة Railway فقط:

## 1) Bucket سحابي (اختياري لكن موصى به للنسخ الخارجي)

1. Railway → Create → **Bucket**
2. خدمة الويب → **Variables** → **Variable References** → اختر **AWS SDK**
3. **Redeploy**
4. افتح `/api/health` وتأكد: `object_storage.cloud_ready = true`

بدون Bucket: التخزين على Volume المحلي جاهز للإنتاج، والنسخ المرآة تعمل محلياً.

## 2) Postgres ظلّي (اختياري)

1. أضف Postgres أو ضع `DATABASE_URL` / `LQ_DATABASE_URL`
2. Redeploy
3. من الواجهة: التوسع المؤسسي → فحص / نسخ ظلّي

الأساس يبقى SQLite على `/app/data`.

## 3) Webhook خارجي (اختياري)

- `LQ_OFFSITE_BACKUP_URL`
- اختياري: `LQ_OFFSITE_BACKUP_TOKEN`

## لا تفعل

- لا تُعدّل كلمات مرور المستخدمين الحاليين من المتغيرات
- لا تحذف Volume `/app/data`
