# تشغيل جودة الانطلاقة — دليل حي (v60)

## الإنتاج
- الموقع: https://web-production-08d73.up.railway.app
- تحديث كاش: https://web-production-08d73.up.railway.app/fresh
- ويندوز: https://web-production-08d73.up.railway.app/get-windows
- الإصدار: `Launch-Quality-LLC-v60-ops-complete`

## قاعدة البيانات
- المسار: `/app/data/jawdah.sqlite3`
- Volume مطلوب على `/app/data`
- محرك الإنتاج: **SQLite** (Postgres ظلّي اختياري)

## النسخ الاحتياطي
- تلقائي يومي في `/app/data/backups`
- مرآة Off-site محلية: `/app/data/offsite-mirror`
- من الواجهة: نسخ احتياطي الآن  
- API: `POST /api/backup/run`
- تحقق: `GET /api/backup/verify` (نجاح عند critical OK ودرجة ≥ 95%)

## جاهزية التشغيل
- `GET /api/platform_readiness` → درجة المنصة
- `GET /api/operations_check` → `platform_score` منفصل عن بيانات الأعمال الفارغة (real-only)
- بيانات العقارات/العملاء/العقود تُدخل يدوياً — لا بيانات تجريبية

## الأمان
- MFA عبر تطبيق المصادقة (TOTP) بدون SMTP
- أجهزة موثوقة + تدوير كلمات المرور 90 يوماً

## استعادة طوارئ
1. أوقف الخدمة
2. استبدل `jawdah.sqlite3` من `/app/data/backups` أو `/app/data/offsite-mirror/latest`
3. استعد `uploads/` إن لزم
4. شغّل وتحقق من `/api/health` ثم تسجيل الدخول
