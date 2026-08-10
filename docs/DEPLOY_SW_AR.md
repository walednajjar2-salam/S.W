# نشر S.W على Railway — دليل كامل

## 1) إنشاء مشروع Railway

1. https://railway.app/dashboard
2. **New Project** → **Deploy from GitHub Repo**
3. اختر: **walednajjar2-salam/S.W**
4. Railway يبني من `Dockerfile` تلقائياً

---

## 2) Volume (مهم — حفظ البيانات)

1. داخل المشروع → خدمة **web** → **Volumes**
2. **Add Volume**
3. Mount path: **`/app/data`**
4. Redeploy

> **مهم:** مع Volume يجب **منطقة واحدة + replica واحد** فقط.  
> إذا ظهر: *Multiple region deployments are not supported with volumes*  
> → **Settings → Scaling** → منطقة واحدة، Replicas = 1.

---

## 2b) Scaling (منطقة واحدة)

1. **Settings → Scaling / Regions**
2. اترك **منطقة واحدة** فقط (مثلاً US East)
3. **Replicas = 1**
4. Start Command = **`./start.sh`** أو **فارغ**

---

## 3) Variables

| Variable | Value |
|----------|--------|
| `SMM_ADMIN_EMAIL` | `walednajjar2@gmail.com` |
| `SMM_ADMIN_PASSWORD` | `najjar` |
| `SMM_SECRET_KEY` | نص سري طويل عشوائي |
| `SMM_DATABASE_PATH` | `/app/data/panel.db` |

> `PORT` يُحقن تلقائياً من Railway — **لا تضعه يدوياً**

---

## 4) Domain

**Settings → Networking → Generate Domain**

افتح: `https://YOUR-DOMAIN.up.railway.app/login`

---

## 5) التحقق

```text
GET https://YOUR-DOMAIN.up.railway.app/api/health
```

المتوقع:

```json
{
  "ok": true,
  "service": "S.W",
  "mode": "simulation",
  "bots": false
}
```

---

## حساب المدير

| البريد | كلمة المرور |
|--------|-------------|
| walednajjar2@gmail.com | najjar |

---

## اختبار محلي قبل النشر

```bash
python3 scripts/verify_production.py
```

---

## Dockerfile

- Python 3.12
- Health check على `/api/health`
- بيانات SQLite على `/app/data/panel.db`
