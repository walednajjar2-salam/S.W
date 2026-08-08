# التطوير المؤسسي — قاعدة النظام

هذه هي **قاعدة التطوير الافتراضية** لنظام Launch Quality ERP بدءاً من v50.

## الهوية

| الحقل | القيمة |
|------|--------|
| الاسم العربي | التطوير المؤسسي |
| الرمز | `terrifying-dev` |
| إصدار الخادم | `Launch-Quality-LLC-v50-terrifying-dev` |
| واجهة | `2026.3-TD` |

## ماذا تفعل القاعدة؟

1. تُفعَّل تلقائياً عند الدخول إلى التطبيق (`body.lq-edition-terrifying`).
2. تحافظ على فاعلية اللوحة (Hub موسّع، Cockpit ظاهر، لا فراغ علوي).
3. تعرض شارة **قاعدة النظام** في الهيدر.
4. تفحص `/api/health` وتدمج النتيجة في `LAUNCH_QUALITY_CHECK()` و `LQ_TERRIFYING_CHECK()`.

## الملفات

- `public/lq-edition-terrifying.css`
- `public/lq-edition-terrifying.js`
- `server.py` → `APP_BASE_EDITION` / `APP_EDITION_LABEL`
- ربط في `public/app.html` و `public/app.js`

## متغيرات البيئة (اختياري)

- `LQ_BASE_EDITION` (افتراضي: `terrifying-dev`)
- `LQ_EDITION_LABEL` (افتراضي: `التطوير المؤسسي`)
- `LQ_EDITION` يبقى `official` في الإنتاج لتجنب بيانات تجريبية

## فحص سريع في المتصفح

```js
LQ_TERRIFYING_CHECK()
LAUNCH_QUALITY_CHECK()
```

## تحديث الكاش

افتح `/fresh` بعد النشر.
