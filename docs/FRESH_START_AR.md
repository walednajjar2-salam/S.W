# NAJJAR Trading — بداية جديدة

> تم تنظيف GitHub. اتبع الخطوات أدناه لمسح Railway وإنشاء نشر جديد.

## ما تم تنفيذه تلقائياً (GitHub)

- حذف **126 فرع** قديم (`cursor/*` و `master`)
- بقي فرع **`main` فقط**
- تاريخ Git جديد — commit واحد نظيف

## ما يجب أن تفعله أنت (5 دقائق)

### 1) مسح مشاريع Railway القديمة (7 مشاريع مكررة)

1. افتح https://railway.app/dashboard
2. لكل مشروع مربوط بالريبو — **Settings → Danger → Delete Project**:
   - heartfelt-growth
   - chic-ambition
   - resilient-commitment
   - glistening-respect
   - proactive-quietude
   - outstanding-presence
   - honest-optimism
3. احذف **الكل** — سننشئ مشروعاً واحداً جديداً

### 2) إنشاء Railway جديد (نشر نظيف)

1. Railway → **New Project** → **Deploy from GitHub repo**
2. اختر: `walednajjar2-salam/NAJJAR-_SOMUM-`
3. **Variables:**

| Variable | Value |
|----------|--------|
| `JAWDAH_HOST` | `0.0.0.0` |
| `JAWDAH_DATA_DIR` | `/app/data` |

4. **Volumes** → Mount path: `/app/data`
5. **Settings → Networking → Generate Domain**
6. انسخ الرابط الجديد (مثل `https://xxx.up.railway.app`)

### 3) تحديث الرابط في المشروع (بعد حصولك على Domain جديد)

أرسل الرابط الجديد للـ Agent ليحدّث:
- `scripts/najjar_app_url.sh`
- `public/get-windows.html`
- `public/releases/windows/*.ps1`
- `public/releases/windows/NAJJAR-Trading.url`

### 4) حذف المستودعات الزائدة (اختياري — من GitHub يدوياً)

الـ Agent **لا يملك صلاحية** حذف المستودعات. احذفها من المتصفح:

| المستودع | الرابط |
|----------|--------|
| NAJJAR-auto-ads | https://github.com/walednajjar2-salam/NAJJAR-auto-ads/settings → Delete |
| launch-quality-mobile | https://github.com/walednajjar2-salam/launch-quality-mobile/settings → Delete |

**احتفظ بـ:** `NAJJAR-_SOMUM-` (المشروع الرئيسي)

### 5) جعل المستودع Private (موصى به)

https://github.com/walednajjar2-salam/NAJJAR-_SOMUM-/settings  
→ Danger Zone → **Change visibility → Private**

---

## حسابات الفريق (بعد النشر)

| Username | Password | Role |
|----------|----------|------|
| waleed.najjar | 1 | owner |
| hamad.sumoom | 2 | owner |
| sara | 3 | operations |
| sales | 4 | sales |
| accounting | 5 | accountant |

---

## تثبيت Windows (بدون EXE — بدون تحذير)

1. افتح `/get-windows` على الرابط الجديد
2. انسخ أمر PowerShell → الصق في PowerShell → Enter

---

## الدعم

بعد إنشاء Railway جديد، أرسل الرابط لتحديث كل الروابط في المشروع.
