# التحصيل الذكي — v51

## ماذا يفعل؟
- يحسب أعمار الذمم: حالي · 1–30 · 31–60 · 61–90 · 90+
- يعرض قائمة الفواتير المفتوحة والمتأخرة
- يرسل تذكيرات: Email / WhatsApp / SMS / سجل داخلي

## أين تجده؟
القائمة → **التحصيل الذكي** أو من قسم الفواتير.

## واجهات API
- `GET /api/receivables/aging`
- `GET /api/receivables/reminders`
- `POST /api/receivables/reminders` `{ channel, bucket?, invoice_ids? }`

## تفعيل القنوات (Railway Variables)
| المتغير | الوظيفة |
|---------|---------|
| `LQ_SMTP_HOST` (+ USER/PASS/FROM) | بريد التذكير |
| `LQ_WHATSAPP_ENABLED=1` | طابور واتساب |
| `LQ_SMS_ENABLED=1` | طابور SMS |

بدون SMTP يبقى زر **تسجيل تذكير** يعمل ويحفظ السجل في النظام.
