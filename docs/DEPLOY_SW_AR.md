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

---

## 3) Variables

| Variable | Value |
|----------|--------|
| `SMM_ADMIN_EMAIL` | `walednajjar2@gmail.com` |
| `SMM_ADMIN_PASSWORD` | `najjar` |
| `SMM_SECRET_KEY` | نص سري طويل عشوائي |
| `SMM_DATABASE_PATH` | `/app/data/panel.db` |
| `SMM_PUBLIC_BASE_URL` | `https://YOUR-DOMAIN.up.railway.app` |
| `SMM_INSTAGRAM_CLIENT_ID` | (اختياري) OAuth إنستجرام |
| `SMM_INSTAGRAM_CLIENT_SECRET` | (اختياري) OAuth إنستجرام |
| `SMM_TIKTOK_CLIENT_KEY` | (اختياري) OAuth تيك توك |
| `SMM_TIKTOK_CLIENT_SECRET` | (اختياري) OAuth تيك توك |

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
