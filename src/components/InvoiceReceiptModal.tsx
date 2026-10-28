import React from 'react';
import { Invoice, ShopSettings } from '../types';
import { formatCurrency, formatWeight } from '../services/currencyService';
import { Printer, Check, X, FileText } from 'lucide-react';

interface InvoiceReceiptModalProps {
  invoice: Invoice | null;
  settings: ShopSettings;
  onClose: () => void;
}

export const InvoiceReceiptModal: React.FC<InvoiceReceiptModalProps> = ({
  invoice,
  settings,
  onClose,
}) => {
  if (!invoice) return null;

  const handlePrint = () => {
    window.print();
  };

  const invoiceDate = new Date(invoice.createdAt);
  const formattedDate = invoiceDate.toLocaleDateString('fa-IR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'Asia/Tehran',
  });
  const formattedTime = invoiceDate.toLocaleTimeString('fa-IR', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Tehran',
  });

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex items-center justify-center p-3 sm:p-6 overflow-y-auto">
      <div className="bg-stone-900 border border-stone-700 rounded-2xl max-w-lg w-full shadow-2xl overflow-hidden flex flex-col my-auto max-h-[92vh]">
        {/* Top Control Header */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-stone-800/80 border-b border-stone-700">
          <div className="flex items-center gap-2 text-white font-bold text-sm">
            <FileText className="w-4 h-4 text-emerald-400" />
            <span>رسید رسمی فاکتور فروش</span>
            <span className="font-mono text-xs text-amber-400 font-normal">
              {invoice.invoiceNumber}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handlePrint}
              className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold px-3 py-1.5 rounded-lg shadow transition cursor-pointer"
            >
              <Printer className="w-3.5 h-3.5" />
              <span>چاپ فاکتور (A5)</span>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-stone-400 hover:text-white rounded-lg hover:bg-stone-700 transition cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Scrollable Receipt Area */}
        <div className="p-4 sm:p-6 overflow-y-auto flex justify-center bg-stone-950/70">
          {/* 80mm Printable Receipt Container */}
          <div
            id="printable-receipt"
            className="w-full max-w-[340px] bg-white text-black p-4 rounded-xl shadow-lg font-sans text-xs leading-relaxed border border-stone-300"
          >
            {/* Store Header */}
            <div className="text-center border-b border-dashed border-stone-400 pb-3 mb-3">
              <div className="text-xl mb-1">🥩</div>
              <h2 className="font-black text-base text-stone-900 tracking-tight">
                {settings.shopName}
              </h2>
              {settings.tagline && (
                <p className="text-[11px] text-stone-600 font-medium">{settings.tagline}</p>
              )}
              {settings.phone && (
                <p className="text-[11px] text-stone-600 font-mono-digits mt-0.5">
                  تلفن تماس: {settings.phone}
                </p>
              )}
              {settings.address && (
                <p className="text-[10px] text-stone-500 mt-0.5 leading-snug">{settings.address}</p>
              )}
            </div>

            {/* Invoice Meta */}
            <div className="border-b border-dashed border-stone-400 pb-2 mb-3 text-[11px] space-y-1">
              <div className="flex justify-between">
                <span className="text-stone-600">شماره فاکتور:</span>
                <span className="font-bold font-mono font-mono-digits">{invoice.invoiceNumber}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-stone-600">تاریخ و ساعت:</span>
                <span className="font-medium font-mono-digits">
                  {formattedDate} - {formattedTime}
                </span>
              </div>
              {invoice.customerName && (
                <div className="flex justify-between">
                  <span className="text-stone-600">نام خریدار:</span>
                  <span className="font-bold">{invoice.customerName}</span>
                </div>
              )}
              {invoice.customerPhone && (
                <div className="flex justify-between">
                  <span className="text-stone-600">تلفن خریدار:</span>
                  <span className="font-mono font-mono-digits">{invoice.customerPhone}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-stone-600">نحوه پرداخت:</span>
                <span className="font-bold">
                  {invoice.paymentMethod === 'card'
                    ? 'کارتخوان (POS)'
                    : invoice.paymentMethod === 'cash'
                    ? 'نقدی'
                    : 'نسیه / اعتباری'}
                </span>
              </div>
            </div>

            {/* Items Table */}
            <table className="w-full text-right text-[11px] mb-3 border-collapse">
              <thead>
                <tr className="border-b border-stone-800 text-stone-700 font-bold">
                  <th className="py-1">شرح کالا</th>
                  <th className="py-1 text-center">وزن (kg)</th>
                  <th className="py-1 text-left">مبلغ کل</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-200">
                {invoice.items.map((item) => (
                  <tr key={item.id} className="align-top">
                    <td className="py-1.5 font-medium">
                      <div>{item.productName}</div>
                      <div className="text-[10px] text-stone-500 font-mono-digits">
                        فی: {formatCurrency(item.unitPriceRial, settings.currencyDisplayUnit, { withUnitLabel: false })}
                      </div>
                    </td>
                    <td className="py-1.5 text-center font-mono-digits whitespace-nowrap">
                      {formatWeight(item.weightKg, { withUnit: false })}
                    </td>
                    <td className="py-1.5 text-left font-mono-digits font-bold whitespace-nowrap">
                      {formatCurrency(item.totalRial, settings.currencyDisplayUnit)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Totals Summary */}
            <div className="border-t-2 border-stone-900 pt-2 space-y-1.5 text-[11px]">
              <div className="flex justify-between text-stone-700">
                <span>مجموع وزن کل:</span>
                <span className="font-bold font-mono-digits">
                  {formatWeight(invoice.totalWeightKg)}
                </span>
              </div>
              <div className="flex justify-between text-stone-700">
                <span>جمع اقلام:</span>
                <span className="font-bold font-mono-digits">
                  {formatCurrency(invoice.subtotalRial, settings.currencyDisplayUnit)}
                </span>
              </div>

              {invoice.discountRial > 0 && (
                <div className="flex justify-between text-rose-700">
                  <span>تخفیف:</span>
                  <span className="font-bold font-mono-digits">
                    - {formatCurrency(invoice.discountRial, settings.currencyDisplayUnit)}
                  </span>
                </div>
              )}

              {invoice.taxRial > 0 && (
                <div className="flex justify-between text-stone-700">
                  <span>مالیات بر ارزش افزوده:</span>
                  <span className="font-bold font-mono-digits">
                    + {formatCurrency(invoice.taxRial, settings.currencyDisplayUnit)}
                  </span>
                </div>
              )}

              {/* Grand Total */}
              <div className="border-t border-dashed border-stone-400 pt-2 mt-2 flex justify-between items-baseline font-black text-sm text-stone-900">
                <span>مبلغ نهایی:</span>
                <span className="text-base font-mono-digits">
                  {formatCurrency(invoice.finalAmountRial, settings.currencyDisplayUnit)}
                </span>
              </div>
              <div className="text-[10px] text-stone-500 text-left font-mono-digits">
                {settings.currencyDisplayUnit === 'TOMAN'
                  ? `(معادل ${formatCurrency(invoice.finalAmountRial, 'RIAL')})`
                  : `(معادل ${formatCurrency(invoice.finalAmountRial, 'TOMAN')})`}
              </div>
            </div>

            {/* Footer */}
            <div className="border-t border-dashed border-stone-400 mt-4 pt-3 text-center text-[10px] text-stone-500 space-y-1">
              <p>{settings.receiptFooter}</p>
              <p className="font-mono text-[9px] text-stone-400">
                سیستم توزین KELI XK3118T1 • MeatShop v2.0
              </p>
            </div>
          </div>
        </div>

        {/* Footer actions */}
        <div className="flex items-center justify-between px-5 py-3 bg-stone-900 border-t border-stone-800">
          <span className="text-xs text-stone-400">
            فاکتور با موفقیت در پایگاه داده محلی ذخیره شد.
          </span>
          <button
            onClick={onClose}
            className="flex items-center gap-1.5 bg-rose-700 hover:bg-rose-600 text-white text-xs font-bold px-4 py-2 rounded-xl transition cursor-pointer"
          >
            <Check className="w-4 h-4" />
            <span>بستن و فاکتور بعدی</span>
          </button>
        </div>
      </div>
    </div>
  );
};
