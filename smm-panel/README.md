# لوحة خدمات — نموذج تعليمي

نظام يحاكي **هيكل مواقع SMM** (Social Media Marketing panels) للتعلم — **بدون بوتات** وبدون أي اتصال بإنستجرام أو تيك توك.

## الميزات

| المكوّن | الوصف |
|---------|--------|
| **حسابات** | تسجيل، دخول، JWT، أدوار (user / admin) |
| **كتالوج خدمات** | متابعين، لايكات، مشاهدات (أسماء تجريبية) |
| **ربط إنستجرام وتيك توك** | ربط يدوي أو OAuth رسمي (Instagram Login + TikTok Login Kit) |
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

افتح: **http://localhost:8090/login**

## حساب المدير

| الاسم | البريد | كلمة المرور | الرصيد |
|-------|--------|-------------|--------|
| Najjar | walednajjar2@gmail.com | najjar | $1000 |

التسجيل العام **مغلق بدون كود دعوة**. المدير يولّد الحسابات أو ينشئ كود دعوة من لوحة الإدارة.

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

## ربط إنستجرام وتيك توك (رسمي)

من اللوحة → **ربط الحسابات** → **ربط رسمي عبر Instagram / TikTok**.

1. المدير يحفظ مفاتيح التطبيق داخل اللوحة (أو عبر متغيرات Railway).
2. انسخ Redirect URI الظاهر في اللوحة إلى:
   - Meta: Instagram API setup with Instagram login → OAuth redirect URIs
   - TikTok: Login Kit → Redirect URI
3. اضغط زر الربط الرسمي. يفتح إنستجرام أو تيك توك لتوثيق الحساب.

الحساب المطلوب لإنستجرام: **Business أو Creator** (ليس حساباً شخصياً عادياً).

يمكن أيضاً لصق `@username` يدوياً كبديل بدون مفاتيح.

Redirect URIs:

- `{BASE}/api/social/oauth/instagram/callback`
- `{BASE}/api/social/oauth/tiktok/callback`

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

**لا يوجد** إرسال متابعين حقيقي لأي منصة. الربط يُستخدم للتحقق من الحساب والرابط فقط.

## متغيرات البيئة (اختياري)

```bash
export SMM_SECRET_KEY="your-secret"
export SMM_DELIVERY_INTERVAL_SECONDS=2
export SMM_ADMIN_EMAIL=walednajjar2@gmail.com
export SMM_ADMIN_PASSWORD=najjar
```

## ⚠️ تنبيه

هذا المشروع **للتعليم فقط**. لا تستخدمه لبيع متابعers وهميين — المنصات تمنع ذلك وقد يضر حسابات حقيقية.

## توليد الحسابات وأكواد الدعوة

من لوحة الإدارة (حساب Najjar):

1. **توليد حسابات:** حتى **1000 حساب في حزمة واحدة** (زر «حزمة 1000»). كلمة المرور موحدة للحزمة.
2. **ربط تلقائي:** عند التوليد يُربط كل حساب بإنستجرام وتيك توك داخل اللوحة (`@user1` …) ويُستخدم الرابط تلقائياً في الطلبات.
3. **كود دعوة:** أنشئ كوداً مثل `SW-XXXXXXXX` ثم شاركه. التسجيل من `/register` يعمل فقط بهذا الكود.

```
POST /api/admin/users/generate
POST /api/admin/invite-codes
POST /api/auth/register   { invite_code, name, email, password }
```

- `GET /api/health` — حالة النظام
- `POST /api/auth/login` — دخول
- `GET /api/services` — قائمة الخدمات
- `POST /api/orders` — طلب جديد
- `GET /api/orders` — الطلبات
- `POST /api/wallet/topup` — شحن تجريبي
