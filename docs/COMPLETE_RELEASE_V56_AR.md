# الإصدار الكامل v56

## ما اكتمل

1. **مركز استيراد الرواتب والحضور** — AGLog / كشف رواتب / تفاصيل بصمات / تعديلات يدوية
2. **تطبيق ويندوز** — ZIP + EXE + صفحة `/get-windows` + زر من شاشة الدخول
3. **أمان الدخول**
   - ثقة الجهاز (`trusted_devices`) مع «تذكرني»
   - تدوير كلمات المرور كل 90 يوماً (`LQ_PASSWORD_MAX_AGE_DAYS`)
   - MFA ناعم لأدوار owner/admin عند جهاز غير موثوق (`LQ_MFA_ENFORCE=soft`)
4. **تصدير الرواتب** يشمل رقم الموظف والمشروع

## روابط سريعة

- الإنتاج: https://web-production-08d73.up.railway.app/fresh
- ويندوز: https://web-production-08d73.up.railway.app/get-windows
- ZIP: https://web-production-08d73.up.railway.app/lq-portable.zip
- EXE: https://web-production-08d73.up.railway.app/lq-setup.exe
- عينات رواتب: `/releases/payroll/sample-payroll-sheet.csv`

## متغيرات اختيارية

| المتغير | الافتراضي | المعنى |
|---------|-----------|--------|
| `LQ_MFA_ENFORCE` | `soft` | `off` / `soft` / `strict` |
| `LQ_MFA_ROLES` | `owner,admin` | الأدوار التي تحتاج MFA |
| `LQ_PASSWORD_MAX_AGE_DAYS` | `90` | `0` لتعطيل التدوير |
| `LQ_DEVICE_TRUST_DAYS` | `30` | مدة ثقة الجهاز |
| `LQ_OTP_DEBUG` | — | يطبع OTP في اللوج إن فشل البريد |
