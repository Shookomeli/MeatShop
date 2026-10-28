import React, { useState } from 'react';
import { InvoiceItem, ShopSettings, Invoice } from '../types';
import { formatCurrency, toPersianDigits, formatWeight, tomanToRial } from '../services/currencyService';
import {
  Receipt,
  Trash2,
  Printer,
  CreditCard,
  Banknote,
  Clock,
  User,
  Phone,
  Tag,
  Scale,
  MinusCircle,
  Percent,
} from 'lucide-react';

interface InvoiceBuilderProps {
  items: InvoiceItem[];
  settings: ShopSettings;
  onRemoveItem: (id: string) => void;
  onClearInvoice: () => void;
  onFinalizeInvoice: (invoice: Invoice) => void;
  onTareScale: () => void;
  onClearScaleWeight: () => void;
}

export const InvoiceBuilder: React.FC<InvoiceBuilderProps> = ({
  items,
  settings,
  onRemoveItem,
  onClearInvoice,
  onFinalizeInvoice,
  onTareScale,
  onClearScaleWeight,
}) => {
  const [customerName, setCustomerName] = useState<string>('');
  const [customerPhone, setCustomerPhone] = useState<string>('');
  const [paymentMethod, setPaymentMethod] = useState<'card' | 'cash' | 'credit'>('card');
  const [discountInput, setDiscountInput] = useState<string>('');
  const [applyTax, setApplyTax] = useState<boolean>(false);
  const [notes, setNotes] = useState<string>('');

  // Calculations (always stored in Rial)
  const totalWeightKg = items.reduce((sum, item) => sum + item.weightKg, 0);
  const subtotalRial = items.reduce((sum, item) => sum + item.totalRial, 0);

  // Discount conversion based on currency display unit
  const discountNumeric = parseFloat(discountInput) || 0;
  const discountRial =
    settings.currencyDisplayUnit === 'TOMAN'
      ? tomanToRial(discountNumeric)
      : Math.round(discountNumeric);

  const effectiveDiscountRial = Math.min(subtotalRial, Math.max(0, discountRial));

  const afterDiscountRial = subtotalRial - effectiveDiscountRial;
  const taxRial = applyTax && settings.taxPercent > 0
    ? Math.round(afterDiscountRial * (settings.taxPercent / 100))
    : 0;

  const finalAmountRial = Math.max(0, afterDiscountRial + taxRial);

  const handleFinalize = () => {
    if (items.length === 0) return;

    // Generate Invoice Number format: INV-YYMMDD-RAND
    const now = new Date();
    const invNumber = `INV-${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(
      now.getDate()
    ).padStart(2, '0')}-${Math.floor(1000 + Math.random() * 9000)}`;

    const newInvoice: Invoice = {
      id: `inv-${Date.now()}`,
      invoiceNumber: invNumber,
      createdAt: now.toISOString(),
      items: [...items],
      totalWeightKg: Math.round(totalWeightKg * 1000) / 1000,
      subtotalRial,
      discountRial: effectiveDiscountRial,
      taxRial,
      finalAmountRial,
      customerName: customerName.trim() || undefined,
      customerPhone: customerPhone.trim() || undefined,
      paymentMethod,
      notes: notes.trim() || undefined,
    };

    onFinalizeInvoice(newInvoice);

    // Reset customer and fields
    setCustomerName('');
    setCustomerPhone('');
    setDiscountInput('');
    setNotes('');
  };

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-2xl p-4 sm:p-5 shadow-xl flex flex-col h-full">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-stone-800 pb-3 mb-3">
        <div className="flex items-center gap-2">
          <div className="bg-rose-950 text-rose-400 p-1.5 rounded-lg border border-rose-800">
            <Receipt className="w-5 h-5" />
          </div>
          <div>
            <h2 className="font-bold text-white text-base">پیش‌نویس فاکتور فروش</h2>
            <span className="text-xs text-stone-400">
              {items.length > 0
                ? `${toPersianDigits(items.length)} ردیف کالا وزن‌کشی شده`
                : 'هنوز کالایی افزوده نشده است'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={onTareScale}
            title="پارسنگ سریع ترازو"
            className="p-1.5 text-sky-400 hover:bg-stone-800 rounded-lg transition"
          >
            <MinusCircle className="w-4 h-4" />
          </button>
          <button
            onClick={onClearScaleWeight}
            title="تخلیه وزن ترازو"
            className="p-1.5 text-stone-400 hover:text-white hover:bg-stone-800 rounded-lg transition"
          >
            <Scale className="w-4 h-4" />
          </button>
          {items.length > 0 && (
            <button
              onClick={onClearInvoice}
              className="flex items-center gap-1 text-xs text-stone-400 hover:text-rose-400 px-2 py-1 rounded hover:bg-stone-800 transition"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>پاک کردن</span>
            </button>
          )}
        </div>
      </div>

      {/* Customer Info Form (Optional) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3 bg-stone-950/60 p-2.5 rounded-xl border border-stone-800/80">
        <div className="relative">
          <input
            type="text"
            placeholder="نام مشتری (اختیاری)"
            value={customerName}
            onChange={(e) => setCustomerName(e.target.value)}
            className="w-full bg-stone-900 border border-stone-800 rounded-lg px-3 py-1.5 pr-8 text-xs text-stone-200 placeholder-stone-500 focus:outline-none focus:border-rose-500"
          />
          <User className="w-3.5 h-3.5 text-stone-500 absolute right-2.5 top-2.5" />
        </div>
        <div className="relative">
          <input
            type="text"
            placeholder="شماره تماس (اختیاری)"
            value={customerPhone}
            onChange={(e) => setCustomerPhone(e.target.value)}
            className="w-full bg-stone-900 border border-stone-800 rounded-lg px-3 py-1.5 pr-8 text-xs text-stone-200 placeholder-stone-500 focus:outline-none focus:border-rose-500 font-mono-digits"
            dir="ltr"
          />
          <Phone className="w-3.5 h-3.5 text-stone-500 absolute right-2.5 top-2.5" />
        </div>
      </div>

      {/* Line Items List */}
      <div className="flex-1 overflow-y-auto space-y-2 min-h-[160px] max-h-[300px] mb-3 pr-1">
        {items.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-stone-500 border border-dashed border-stone-800 rounded-xl">
            <Scale className="w-10 h-10 mb-2 text-stone-600" />
            <p className="text-sm font-medium text-stone-400">فاکتور جاری خالی است</p>
            <p className="text-xs text-stone-500 mt-1 max-w-xs">
              گوشت یا مرغ را روی کفه ترازو بگذارید و محصول موردنظر را از فهرست سمت راست انتخاب کنید.
            </p>
          </div>
        ) : (
          items.map((item, index) => (
            <div
              key={item.id}
              className="bg-stone-950/80 border border-stone-800/80 rounded-xl p-2.5 flex items-center justify-between text-xs hover:border-stone-700 transition"
            >
              <div className="flex items-center gap-2.5">
                <span className="w-5 h-5 rounded-full bg-stone-900 border border-stone-800 text-stone-400 flex items-center justify-center font-mono-digits text-[11px]">
                  {toPersianDigits(index + 1)}
                </span>
                <div>
                  <h4 className="font-bold text-stone-100 text-sm">{item.productName}</h4>
                  <div className="flex items-center gap-3 text-stone-400 text-[11px] mt-0.5">
                    <span>
                      وزن خالص:{' '}
                      <strong className="text-emerald-400 font-bold font-mono-digits">
                        {formatWeight(item.weightKg)}
                      </strong>
                    </span>
                    <span>•</span>
                    <span>
                      نرخ واحد:{' '}
                      <span className="font-mono-digits">
                        {formatCurrency(item.unitPriceRial, settings.currencyDisplayUnit)}
                      </span>
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="text-left font-mono-digits">
                  <span className="text-amber-400 font-bold text-sm block">
                    {formatCurrency(item.totalRial, settings.currencyDisplayUnit)}
                  </span>
                </div>
                <button
                  onClick={() => onRemoveItem(item.id)}
                  title="حذف این ردیف"
                  className="p-1.5 text-stone-400 hover:text-rose-400 hover:bg-stone-800 rounded-lg transition cursor-pointer"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Invoice Totals & Summary Panel */}
      <div className="bg-stone-950 border border-stone-800 rounded-xl p-3.5 space-y-2.5">
        {/* Weight & Subtotal */}
        <div className="flex items-center justify-between text-xs text-stone-400">
          <span>مجموع وزن فاکتور:</span>
          <span className="font-bold text-stone-200 font-mono-digits text-sm">
            {formatWeight(totalWeightKg)}
          </span>
        </div>

        <div className="flex items-center justify-between text-xs text-stone-400">
          <span>جمع اقلام (ناخالص):</span>
          <span className="font-bold text-stone-200 font-mono-digits text-sm">
            {formatCurrency(subtotalRial, settings.currencyDisplayUnit)}
          </span>
        </div>

        {/* Discount Row */}
        <div className="flex items-center justify-between gap-2 pt-1 border-t border-stone-800/80">
          <div className="flex items-center gap-1.5 text-xs text-stone-400">
            <Tag className="w-3.5 h-3.5 text-amber-400" />
            <span>تخفیف ({settings.currencyDisplayUnit === 'TOMAN' ? 'تومان' : 'ریال'}):</span>
          </div>
          <div className="max-w-[130px]">
            <input
              type="number"
              min="0"
              placeholder="۰"
              value={discountInput}
              onChange={(e) => setDiscountInput(e.target.value)}
              className="w-full bg-stone-900 border border-stone-800 rounded px-2 py-1 text-xs text-white text-left font-mono-digits focus:outline-none focus:border-rose-500"
              dir="ltr"
            />
          </div>
        </div>

        {/* VAT / Tax Toggle if shop taxPercent > 0 */}
        {settings.taxPercent > 0 && (
          <div className="flex items-center justify-between pt-1 border-t border-stone-800/80 text-xs">
            <label className="flex items-center gap-1.5 text-stone-400 cursor-pointer">
              <input
                type="checkbox"
                checked={applyTax}
                onChange={(e) => setApplyTax(e.target.checked)}
                className="w-3.5 h-3.5 rounded bg-stone-900 border-stone-700 text-rose-600"
              />
              <Percent className="w-3.5 h-3.5 text-stone-400" />
              <span>محاسبه مالیات بر ارزش افزوده ({toPersianDigits(settings.taxPercent)}٪):</span>
            </label>
            <span className="font-mono-digits text-stone-300">
              {formatCurrency(taxRial, settings.currencyDisplayUnit)}
            </span>
          </div>
        )}

        {/* Final Amount Payable */}
        <div className="pt-2 border-t border-stone-800 flex items-baseline justify-between">
          <div>
            <span className="text-sm font-bold text-white block">مبلغ نهایی قابل پرداخت:</span>
            <span className="text-[11px] text-stone-400">
              {settings.currencyDisplayUnit === 'TOMAN'
                ? `معادل ${formatCurrency(finalAmountRial, 'RIAL')}`
                : `معادل ${formatCurrency(finalAmountRial, 'TOMAN')}`}
            </span>
          </div>
          <div className="text-right">
            <div className="text-xl sm:text-2xl font-black text-emerald-400 font-mono-digits">
              {formatCurrency(finalAmountRial, settings.currencyDisplayUnit)}
            </div>
          </div>
        </div>

        {/* Payment Method Selector */}
        <div className="pt-2 border-t border-stone-800/80">
          <span className="text-[11px] text-stone-400 block mb-1.5">روش تسویه حساب:</span>
          <div className="grid grid-cols-3 gap-1.5">
            {[
              { id: 'card', label: 'کارتخوان (POS)', icon: CreditCard },
              { id: 'cash', label: 'نقدی', icon: Banknote },
              { id: 'credit', label: 'نسیه / حساب دفتری', icon: Clock },
            ].map((p) => {
              const Icon = p.icon;
              const isSelected = paymentMethod === p.id;
              return (
                <button
                  key={p.id}
                  onClick={() => setPaymentMethod(p.id as any)}
                  className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-xs font-medium transition cursor-pointer ${
                    isSelected
                      ? 'bg-rose-700 text-white shadow-sm'
                      : 'bg-stone-900 text-stone-400 hover:bg-stone-800 hover:text-white border border-stone-800'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{p.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Action Buttons: Finalize / Print */}
        <div className="pt-2">
          <button
            onClick={handleFinalize}
            disabled={items.length === 0}
            className="w-full flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:hover:bg-emerald-600 active:scale-98 text-white font-bold py-3 px-4 rounded-xl shadow-lg shadow-emerald-950/50 transition cursor-pointer text-sm"
          >
            <Printer className="w-4 h-4" />
            <span>ثبت نهایی و چاپ فاکتور فروش</span>
          </button>
        </div>
      </div>
    </div>
  );
};
