# برنامج الموظفين — المبيعات والمصاريف ورأس المال

نظام **النجار والسموم للتجارة** للموظفين:

| القسم | الوظيفة |
|-------|---------|
| المبيعات | تسجيل بيع السيارات |
| المصاريف | تسجيل مصاريف الشحن/الجمارك/الصيانة/المكتب |
| رأس المال | مساهمات وسحوبات الشريكين |
| توزيعات رأس المال | توزيع الأرباح 50% / 50% |

## الشريكان

| الشريك | النسبة | المستخدم |
|--------|--------|----------|
| وليد النجار | 50% | `waleed.najjar` |
| حمد السموم | 50% | `hamad.sumoom` |

## الدخول

- لوحة الموظفين: `/auto-trading.html`
- تسجيل الدخول: `/auto-trading/login.html`
- بوابة الزبائن: `/auto-trading/customer.html`

## API

- `GET/POST /api/auto-trading/sales`
- `GET/POST /api/auto-trading/expenses`
- `GET/POST /api/auto-trading/capital`
- `GET/POST /api/auto-trading/distributions`
