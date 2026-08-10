# حذف المنصات القديمة — دليل يدوي

> تم حذف **كود** السيارات والعقارات من هذا المستودع.  
> حذف **GitHub** و **Railway** يتطلب صلاحيات المالك — نفّذها من المتصفح.

---

## ما تم حذفه من الكود (تلقائياً)

| المحذوف | الوصف |
|---------|--------|
| `server.py` | خادم NAJJAR Trading (760K+ سطر) |
| `public/` | واجهات السيارات والعقارات |
| `lq_*.py` | عقارات نزوى، تداول، محاسبة |
| `mobile/` | تطبيق Android WebView |
| `tools/` | Launcher ويندوز |
| `scripts/` | سكربتات النشر والاختبار |
| `railway.toml`, `RAILWAY.md` | إعدادات Railway |
| `Dockerfile`, `fly.toml`, `render.yaml` | نشر قديم |

**المتبقي:** `smm-panel/` فقط.

---

## 1) حذف مشاريع Railway (يدوياً — ~5 دقائق)

1. افتح https://railway.app/dashboard
2. لكل مشروع مربوط بالريبو القديم:
   - **Settings → Danger Zone → Delete Project**
3. المشاريع المعروفة سابقاً (احذف الكل):
   - heartfelt-growth
   - chic-ambition
   - resilient-commitment
   - glistening-respect
   - proactive-quietude
   - outstanding-presence
   - honest-optimism
   - أي مشروع يشير إلى `web-production-08d73.up.railway.app`

بعد الحذف: **لا يوجد** نشر حي للمنصة القديمة.

---

## 2) حذف مستودعات GitHub (يدوياً)

الـ Agent **لا يملك صلاحية** `repo:delete`. احذف من المتصفح:

| المستودع | الرابط |
|----------|--------|
| NAJJAR-auto-ads | https://github.com/walednajjar2-salam/NAJJAR-auto-ads/settings → Delete |
| launch-quality-mobile | https://github.com/walednajjar2-salam/launch-quality-mobile/settings → Delete |
| NAJJAR-_SOMUM- | https://github.com/walednajjar2-salam/NAJJAR-_SOMUM-/settings → Delete *(إن أردت حذف الكل)* |

**بديل:** احتفظ بـ `NAJJAR-_SOMUM-` وادفع فرع `main` الجديد (يحتوي `smm-panel` فقط).

---

## 3) إن أردت مستودعاً جديداً نظيفاً

```bash
# محلياً بعد clone
git remote remove origin
gh repo create my-smm-panel --private --source=. --push
```

---

## 4) التحقق

- [ ] Railway: لا مشاريع نشطة للمنصة القديمة
- [ ] GitHub: المستودعات الزائدة محذوفة أو خاصة
- [ ] محلياً: `python smm-panel/run.py` يعمل على المنفذ 8090
