# التخزين الدائم + النسخ (v59)

## جاهز الآن بدون Bucket
- الملفات على Volume: `/app/data/uploads`
- مرآة النسخ الاحتياطي: `/app/data/offsite-mirror`
- الوضع: `local-durable` + offsite `local-volume`

## Bucket اختياري (نسخ سحابي إضافي)
1. Railway → Create → Bucket
2. خدمة النظام → Variables → Variable References → AWS SDK
3. Redeploy

بعد الربط يتحول الوضع إلى `cloud` / `object-storage` تلقائياً.

## أين تفحص؟
- `/api/platform_readiness`
- `/api/health` → `offsite.enabled` و `object_storage.ready`
- التوسع المؤسسي → بطاقة الجاهزية
