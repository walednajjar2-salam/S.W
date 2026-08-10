# لوحة خدمات — نموذج تعليمي

نظام يحاكي **هيكل مواقع SMM** (Social Media Marketing panels) للتعلم — **بدون بوتات** وبدون أي اتصال بإنستجرام أو تيك توك.

## الميزات

| المكوّن | الوصف |
|---------|--------|
| **حسابات** | تسجيل، دخول، JWT، أدوار (user / admin) |
| **كتalog خدمات** | متابعين، لايكات، مشاهدات (أسماء تجريبية) |
| **طلبات** | رابط + كمية + خصم من المحفظة |
| **محفظة** | شحن تجريبي (بدون بوابة دفع حقيقية) |
| **Worker** | طابور تسليم **محاكى** — يحدّث `delivered` تلقائياً |
| **لوحة مدير** | إحصائيات، مستخدمون، خدمات، كل الطلبات |

## التشغيل

```bash
cd smm-panel
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

افتح: **http://localhost:8090**

## حساب المدير

| الاسم | البريد | كلمة المرور | الرصيد |
|-------|--------|-------------|--------|
| Najjar | walednajjar2@gmail.com | najjar | $1000 |

التسجيل العام **مغلق** — Najjar فقط.

## هيكل المشروع

```
smm-panel/
├── app/
│   ├── main.py       # FastAPI routes
│   ├── auth.py       # JWT + passwords
│   ├── database.py   # SQLite
│   ├── worker.py     # محاكاة التسليم
│   ├── seed.py       # بيانات أولية
│   └── schemas.py
├── public/
│   ├── index.html
│   └── assets/       # login, panel, CSS, JS
└── run.py
```

## كيف يعمل التسليم (محاكاة)

```
طلب جديد → status: processing
       ↓
Worker (كل ~2 ثانية)
       ↓
delivered += 8% من الكمية
       ↓
delivered >= quantity → status: completed
```

**لا يوجد** HTTP requests لأي منصة.social.

## متغيرات البيئة (اختياري)

```bash
export SMM_SECRET_KEY="your-secret"
export SMM_DELIVERY_INTERVAL_SECONDS=2
export SMM_ADMIN_EMAIL=walednajjar2@gmail.com
export SMM_ADMIN_PASSWORD=najjar
```

## ⚠️ تنبيه

هذا المشروع **للتعليم فقط**. لا تستخدمه لبيع متابعers وهميين — المنصات تمنع ذلك وقد يضر حسابات حقيقية.

## API سريع

- `GET /api/health` — حالة النظام
- `POST /api/auth/login` — دخول
- `GET /api/services` — قائمة الخدمات
- `POST /api/orders` — طلب جديد
- `GET /api/orders` — الطلبات
- `POST /api/wallet/topup` — شحن تجريبي
