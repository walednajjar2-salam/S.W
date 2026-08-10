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

## الخطأ #3 — عدة مناطق + Volume (الخطأ الحالي)

**رسالة Railway:**
```text
Multiple region deployments are not supported with volumes.
```

**السبب:** الخدمة مضبوطة على **عدة regions** (مثلاً asia, europe, sfo, us-east)  
بينما **Volume** (`app-data` على `/app/data`) يعمل **بمنطقة واحدة فقط**.  
SQLite على volume **لا يتحمل** أكثر من نسخة واحدة.

**الحل (من الموبايل):**

1. افتح خدمة **web** → **Settings** → **Scaling** (أو Regions)
2. **احذف** كل المناطق ما عدا **واحدة** (يفضل us-east إن Volume فيها)
3. اضبط **Replicas = 1**
4. **Deploy** من جديد

> تم إضافة `multiRegionConfig` في `railway.toml` لفرض **منطقة واحدة + replica واحد**  
> بعد merge لـ `main`، Railway يطبّق الإعداد تلقائياً على كل deploy.

---

## الخطأ #4 — Bucket اسمه `cursor`

**رسالة محتملة:**
```text
Bucket region undefined is invalid
```

**الحل:** احذف Bucket **`cursor`** — المشروع **ما يحتاجه** (SQLite على Volume كافي).

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
