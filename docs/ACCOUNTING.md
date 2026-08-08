# Accounting module overview

## Available in the UI

| Section | What it does |
|---------|----------------|
| **الحسابات** | Income/expense entries linked to client, property, invoice |
| **الفواتير** | Rent invoices from contracts; payment posts to accounts |
| **فواتير المشتريات** | Supplier AP tracking |
| **الإيرادات** | Other revenue sources |
| **الرواتب** | Payroll (basic, allowances, deductions, net) |
| **مصاريف إدارية** | G&A expenses |
| **المخزن** | Items + stock in/out |
| **كشف البنك** | Bank deposits/withdrawals + optional match to account |
| **دليل الحسابات** | Chart of accounts (COA) — add, edit, export |
| **تسوية البنك** | Book vs bank statement reconciliation with auto book balance |
| **الفترات المالية** | Open/close accounting periods |
| **قائمة الدخل والميزانية** | Auto-generated from live data |

### Accounts hub extras

- AR aging
- Tenant balance statements
- Property profitability
- HTML financial report download
- CSV export

## Backend only (no screen yet)

- Approvals workflow (`approvals`)

## Integration level

**Strong for property management:** contract → invoice → payment → account entry.

**Not a full certified ERP:** no double-entry journal, VAT e-invoicing, or Oman tax audit export out of the box.

## Recommended login for accounting

- `razan.accounting` / `Jawdeh123` (accountant role)
