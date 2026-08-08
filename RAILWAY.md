# Launch Quality LLC — Railway Deploy (Live)

> دليل النشر الحي — جاهزية المنصة على الإنتاج.

## Live production

| | |
|--|--|
| 🌐 **الموقع** | https://web-production-08d73.up.railway.app |
| 🔄 **تحديث كاش** | https://web-production-08d73.up.railway.app/fresh |
| 🪟 **تطبيق ويندوز** | https://web-production-08d73.up.railway.app/get-windows |
| 📱 **تطبيق أندرويد** | https://web-production-08d73.up.railway.app/get-android |
| 🗺️ **خريطة نزوى** | https://www.openstreetmap.org/?mlat=22.9333&mlon=57.5333#map=13/22.9333/57.5333 |
| 📸 **شعار** | https://web-production-08d73.up.railway.app/assets/brand-logo-gold.png |
| 📸 **خلفية الدخول** | https://web-production-08d73.up.railway.app/assets/login-portal-bg.png |
| 📸 **أيقونة** | https://web-production-08d73.up.railway.app/assets/app-icon-512.png |

الإصدار الحالي: **`Launch-Quality-LLC-v70.4-finish-remaining`**

## Health check

```text
GET https://web-production-08d73.up.railway.app/api/health
```

المتوقع:

```json
{
  "ok": true,
  "status": "healthy",
  "service": "production",
  "version": "Launch-Quality-LLC-v70.4-finish-remaining",
  "platform_ready": true,
  "database_engine": "sqlite",
  "stable": true,
  "stable_tag": "v70.4-complete",
  "offsite": { "enabled": true, "mode": "local-volume" }
}
```

جاهزية المنصة (بعد الدخول):

```text
GET /api/platform_readiness
→ platform_score: 100, platform_ready: true
```

## Quick deploy

1. ادفع المستودع إلى GitHub (`main`).
2. Railway → **New Project** → **Deploy from GitHub repo**.
3. Variables:

| Variable | Value |
|----------|--------|
| `JAWDAH_HOST` | `0.0.0.0` |
| `JAWDAH_DATA_DIR` | `/app/data` |

`PORT` يُحقن تلقائياً — لا تضعه يدوياً.

4. **Volumes** → Mount `/app/data` (ضروري لعدم فقدان البيانات).
5. **Settings → Networking → Generate Domain**.

أمر التشغيل: `python server.py` (`Procfile` / `railway.toml`).

## ما هو جاهز بدون إعداد إضافي

- **SQLite** على Volume = قاعدة إنتاج أساسية
- **تخزين محلي دائم** للعقود/الصور على `/app/data/uploads`
- **Off-site محلي** = مرآة نسخ في `/app/data/offsite-mirror`
- **MFA** عبر تطبيق المصادقة (**TOTP**) بدون SMTP
- **أجهزة موثوقة** + تدوير كلمات المرور
- **تطبيقات ويندوز/أندرويد** من `/get-windows` و `/get-android`

## قائمة المالك على Railway (اختياري — لا يُنجز من الكود وحده)

### 1) Railway Bucket (نسخ سحابي إضافي)
1. Create → **Bucket**
2. خدمة web → Variables → **Variable References** → **AWS SDK**
3. Redeploy
4. تحقق من `/api/health` → `object_storage.cloud_ready: true`

### 2) PostgreSQL (ظلّي للتحقق فقط — الأساس يبقى SQLite)
1. أضف Postgres plugin أو ضع `DATABASE_URL` / `LQ_DATABASE_URL`
2. Redeploy
3. الواجهة: التوسع المؤسسي → فحص / نسخ ظلّي / تحقق

### 3) Webhook خارجي (اختياري فوق المرآة المحلية)
- `LQ_OFFSITE_BACKUP_URL` (+ اختياري `LQ_OFFSITE_BACKUP_TOKEN`)

### 4) SMTP / OpenAI / VAT (اختياري)
- SMTP: `LQ_SMTP_HOST` / `LQ_SMTP_PORT` / `LQ_SMTP_USER` / `LQ_SMTP_PASS`
- لا تُعاد كلمات مرور المستخدمين الحاليين عند النشر

## حسابات الفريق

كلمات المرور تُضبط عند أول إنشاء مستخدم ولا تُعاد كتابتها عند كل نشر.  
غيّر كلمات المرور من داخل النظام (تدوير 90 يوماً).

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `502` | انتظر النشر؛ راجع logs لـ `python server.py` |
| فقدان بيانات | تأكد Volume على `/app/data` |
| كاش قديم | افتح `/fresh` |
| MFA | استخدم Google Authenticator بعد أول تحدي TOTP |
| تخزين يظهر محلي | Bucket غير مربوط — راجع قائمة المالك أعلاه |

## UI live checklist

- ✅ روابط الموقع والخريطة والصور أعلاه حية
- ✅ منصات: عقارات / ضيافة / محاسبة بعد الدخول
- ✅ تطبيق ويندوز من `/get-windows`
- ✅ تطبيق أندرويد من `/get-android`
