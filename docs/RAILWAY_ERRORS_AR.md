# أخطاء Railway المكتشفة — S.W

## الخطأ #1 (الرئيسي) — Start Command غلط

**ما كان يشتغل:**
```bash
cd smm-panel && python run.py
```

**السبب:** داخل Docker الملفات في `/app` مباشرة — **ما في** مجلد `smm-panel`.

**النتيجة:**
```
cd: smm-panel: No such file or directory
```
→ التطبيق **يتعطل فوراً** → Deploy **FAILED** → الموقع **404**

**الحل:** Start Command = `./start.sh` أو **فارغ** (يستخدم Dockerfile)

---

## الخطأ #2 — Build نجح، Deploy فشل

| المرحلة | الحالة |
|---------|--------|
| Docker Build | ✅ Success |
| Runtime | ❌ Failed |
| Instances | REMOVED (4) |
| Domain | 404 Application not found |

---

## الخطأ #3 — 4 مناطق (Regions)

المشروع منشور على **4 regions** بنفس الوقت.  
SQLite **ما يشتغل** مع عدة نسخ على نفس الملف.

**الحل:** **Settings → Scaling** → **1 replica** فقط (منطقة واحدة)

---

## Variables المطلوبة

```
SMM_ADMIN_EMAIL=walednajjar2@gmail.com
SMM_ADMIN_PASSWORD=najjar
SMM_DATABASE_PATH=/app/data/panel.db
SMM_SECRET_KEY=sw-najjar-2026
```

## Volume

```
Mount: /app/data
```

---

## بعد الإصلاح

```
https://web-production-f3cc8.up.railway.app/api/health
→ {"ok": true, "service": "S.W"}
```
