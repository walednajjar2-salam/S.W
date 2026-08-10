# S.W — لوحة خدمات

**S.W** — مشروع تعليمي: نظام SMM (طلبات، محفظة، طابور تسليم محاكى) **بدون بوتات**.

المستودع: https://github.com/walednajjar2-salam/S.W

## التشغيل

```bash
cd smm-panel
pip install -r requirements.txt
python run.py
```

افتح: http://localhost:8090/login

## حسابات تجريبية

| الاسم | البريد | كلمة المرور |
|-------|--------|-------------|
| Najjar | walednajjar2@gmail.com | najjar |

راجع [smm-panel/README.md](smm-panel/README.md) للتفاصيل.

## النشر على Railway

راجع **[docs/DEPLOY_SW_AR.md](docs/DEPLOY_SW_AR.md)** — بناء Docker جاهز + Volume + Variables.

```bash
python3 scripts/verify_production.py   # اختبار قبل النشر
```
