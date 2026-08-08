/**
 * Unit test for the printed-document helpers in public/auto-trading/print-docs.js.
 *
 * The Arabic amount-in-words converter is the part worth pinning down: Omani
 * contracts and vouchers state the sum in words as well as figures, and the
 * counted noun changes form with the last two digits of the number.
 *
 * Run: node scripts/test_print_docs.js
 */
const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, '..', 'public', 'auto-trading', 'print-docs.js');

/* A stub window records what a document would have printed, so the templates
   can be asserted on without a browser. */
let printed = null;
const fakeWindow = {
  open() {
    printed = '';
    const doc = {
      write(html) { printed += html; },
      close() {},
      querySelectorAll() { return []; },
      fonts: { ready: Promise.resolve() },
    };
    return { document: doc, focus() {}, print() {} };
  },
};
new Function('window', 'document', fs.readFileSync(SRC, 'utf8'))
  .call(fakeWindow, fakeWindow, {});
const docs = fakeWindow.NajjarPrintDocs;
const { moneyWords } = docs;

const CASES = [
  [0, 'فقط صفر ريال عماني لا غير'],
  [1, 'فقط ريال عماني واحد لا غير'],
  [2, 'فقط ريالان عمانيان لا غير'],
  [3, 'فقط ثلاثة ريالات عمانية لا غير'],
  [11, 'فقط أحد عشر ريالاً عمانياً لا غير'],
  [21, 'فقط واحد وعشرون ريالاً عمانياً لا غير'],
  // A round hundred or thousand takes the genitive singular, not the accusative.
  [100, 'فقط مئة ريال عماني لا غير'],
  [125, 'فقط مئة وخمسة وعشرون ريالاً عمانياً لا غير'],
  [1000, 'فقط ألف ريال عماني لا غير'],
  [1500, 'فقط ألف وخمسمئة ريال عماني لا غير'],
  [2500, 'فقط ألفان وخمسمئة ريال عماني لا غير'],
  [3200, 'فقط ثلاثة آلاف ومئتان ريال عماني لا غير'],
  [12000, 'فقط اثنا عشر ألف ريال عماني لا غير'],
  [125000, 'فقط مئة وخمسة وعشرون ألف ريال عماني لا غير'],
  [1000000, 'فقط مليون ريال عماني لا غير'],
  // Baisa are the thousandths of a rial and are spelled out alongside it.
  [1.5, 'فقط ريال عماني واحد وخمسمئة بيسة لا غير'],
  [0.25, 'فقط مئتان وخمسون بيسة لا غير'],
  [0.001, 'فقط بيسة واحدة لا غير'],
  [4500.75, 'فقط أربعة آلاف وخمسمئة ريال عماني وسبعمئة وخمسون بيسة لا غير'],
];

let failed = 0;
for (const [amount, expected] of CASES) {
  const actual = moneyWords(amount);
  if (actual === expected) continue;
  failed += 1;
  console.error(`FAIL ${amount}\n  got:  ${actual}\n  want: ${expected}`);
}

function check(label, condition) {
  if (condition) return;
  failed += 1;
  console.error(`FAIL ${label}`);
}

const SALE = {
  sale_no: 'AT-S-2026-0001',
  sale_date: '2026-08-07',
  buyer_name: 'سالم الريامي',
  buyer_phone: '99887766',
  sale_price: 4650,
  deposit_amount: 0,
  payment_method: 'نقد',
  stock_no: 'NT-BMW-004',
  make: 'BMW',
  model: '550i',
  vin: 'WBAFR9C55DD226932',
  engine_no: 'X1234',
  plate_no: '61265 / د د',
};
const PLAIN_COMPANY = { address_ar: 'نزوى — الفلج', bank: { iban: 'OM07' }, vat_rate: 5 };
const VAT_COMPANY = { ...PLAIN_COMPANY, cr_no: '1234567', vat_no: 'OM1100112233' };

// The contract must identify the vehicle it transfers and state the sum in words.
docs.printSaleContract(SALE, SALE, PLAIN_COMPANY);
check('sale contract prints the VIN', printed.includes('WBAFR9C55DD226932'));
check('sale contract prints the engine number', printed.includes('X1234'));
check('sale contract prints the plate', printed.includes('61265'));
check('sale contract states the sum in words', printed.includes(moneyWords(4650)));
check('sale contract shows three decimals', printed.includes('4,650.000'));

// Without a VAT registration it is a plain sales invoice, with no tax line.
docs.printSaleInvoice(SALE, SALE, PLAIN_COMPANY);
check('unregistered invoice is not a tax invoice', !printed.includes('Tax Invoice'));
check('unregistered invoice says Sales Invoice', printed.includes('Sales Invoice'));
check('unregistered invoice omits VAT', !printed.includes('ضريبة القيمة المضافة'));
check('unregistered invoice bills the full price', printed.includes('4,650.000'));

// With one, the tax is broken out of the agreed retail price.
docs.printSaleInvoice(SALE, SALE, VAT_COMPANY);
check('registered invoice is a tax invoice', printed.includes('Tax Invoice'));
check('registered invoice shows the VAT rate', printed.includes('ضريبة القيمة المضافة 5%'));
check('registered invoice shows the net of 4650 at 5%', printed.includes('4,428.571'));
check('registered invoice shows the tax of 4650 at 5%', printed.includes('221.429'));
check('registered invoice still totals 4650', printed.includes('4,650.000'));
check('registered invoice prints the VAT number', printed.includes('OM1100112233'));
check('registered invoice prints the CR number', printed.includes('1234567'));

// Vouchers carry the written sum, which is the point of a voucher.
docs.printReceiptVoucher(SALE, PLAIN_COMPANY);
check('receipt voucher states the sum in words', printed.includes(moneyWords(4650)));
docs.printPaymentVoucher({ kind: 'expense', amount: 1500, category: 'شحن', expense_no: 'AT-E-2026-0003' }, PLAIN_COMPANY);
check('payment voucher states the sum in words', printed.includes(moneyWords(1500)));
check('payment voucher reads as a round thousand', printed.includes('فقط ألف وخمسمئة ريال عماني لا غير'));

if (failed) {
  console.error(`\nprint-docs: ${failed} check(s) failed`);
  process.exit(1);
}
console.log(`print-docs: OK (${CASES.length} amount-in-words cases + document checks)`);
