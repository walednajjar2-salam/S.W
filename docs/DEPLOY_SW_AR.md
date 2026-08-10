# نشر S.W على الإنternet

## لماذا `localhost` لا يعمل من الموبايل؟

`localhost` = جهازك فقط. من الموبايل **لن يفتح** إلا بعد **نشر** الموقع.

---

## نشر دائم — Railway (موصى به)

1. https://railway.app/dashboard → **New Project**
2. **Deploy from GitHub repo** → اختر **S.W**
3. Railway يكتشف `Dockerfile` تلقائياً
4. **Variables** (اختياري):

| Variable | Value |
|----------|--------|
| `SMM_ADMIN_EMAIL` | walednajjar2@gmail.com |
| `SMM_ADMIN_PASSWORD` | najjar |
| `SMM_SECRET_KEY` | أي نص سري طويل |

5. **Networking → Generate Domain**
6. افتح: `https://xxx.up.railway.app/login`

---

## نشر — Render

1. https://dashboard.render.com → **New +** → **Blueprint**
2. اربط مستودع **S.W** (يستخدم `render.yaml`)

---

## تشغيل محلي (للتطوير)

```bash
cd smm-panel
pip install -r requirements.txt
python run.py
```

افتح: http://localhost:8090/login

---

## حساب المدير

| البريد | كلمة المرور |
|--------|-------------|
| walednajjar2@gmail.com | najjar |
