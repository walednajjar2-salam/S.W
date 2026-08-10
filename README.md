# لوحة خدمات — مشروع تعليمي

تم إزالة منصة **السيارات والعقارات** القديمة بالكامل.  
المشروع الحالي: **`smm-panel/`** فقط — نظام SMM تعليمي بدون بوتات.

## التشغيل

```bash
cd smm-panel
pip install -r requirements.txt
python run.py
```

افتح: http://localhost:8090

## حسابات تجريبية

| الدور | البريد | كلمة المرور |
|-------|--------|-------------|
| مدير | admin@example.com | admin123 |
| مستخدم | demo@example.com | demo123 |

راجع [smm-panel/README.md](smm-panel/README.md) للتفاصيل.

## حذف Railway والمستودعات القديمة

راجع [docs/CLEANUP_MANUAL_AR.md](docs/CLEANUP_MANUAL_AR.md) — خطوات يدوية (الـ Agent لا يملك صلاحية حذف GitHub/Railway).
