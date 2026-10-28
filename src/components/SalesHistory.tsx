import React, { useState, useMemo } from 'react';
import { Invoice, ShopSettings } from '../types';
import { formatCurrency, toPersianDigits, formatWeight } from '../services/currencyService';
import {
  Search,
  Printer,
  Trash2,
  Scale,
  TrendingUp,
  Receipt,
  Banknote,
  Download,
} from 'lucide-react';

interface SalesHistoryProps {
  invoices: Invoice[];
  settings: ShopSettings;
  onViewInvoice: (invoice: Invoice) => void;
  onDeleteInvoice: (id: string) => void;
}

export const SalesHistory: React.FC<SalesHistoryProps> = ({
  invoices,
  settings,
  onViewInvoice,
  onDeleteInvoice,
}) => {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [filterPayment, setFilterPayment] = useState<string>('all');

  const filteredInvoices = useMemo(() => {
    return invoices.filter((inv) => {
      const matchSearch =
        inv.invoiceNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (inv.customerName && inv.customerName.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (inv.customerPhone && inv.customerPhone.includes(searchQuery));

      const matchPayment = filterPayment === 'all' || inv.paymentMethod === filterPayment;

      return matchSearch && matchPayment;
    });
  }, [invoices, searchQuery, filterPayment]);

  // Aggregate Metrics
  const totalRevenueRial = invoices.reduce((sum, inv) => sum + inv.finalAmountRial, 0);
  const totalWeightSoldKg = invoices.reduce((sum, inv) => sum + inv.totalWeightKg, 0);
  const avgTicketRial = invoices.length > 0 ? Math.round(totalRevenueRial / invoices.length) : 0;

  const handleExportData = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(invoices, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `meat_shop_invoices_backup_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="space-y-4">
      {/* Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Card 1: Total Sales */}
        <div className="bg-stone-900 border border-stone-800 rounded-2xl p-4 shadow-lg flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-emerald-950 text-emerald-400 flex items-center justify-center border border-emerald-800">
            <TrendingUp className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-stone-400 block">مجموع فروش کل</span>
            <div className="text-base sm:text-lg font-bold text-emerald-400 font-mono-digits">
              {formatCurrency(totalRevenueRial, settings.currencyDisplayUnit)}
            </div>
          </div>
        </div>

        {/* Card 2: Total Weight Sold */}
        <div className="bg-stone-900 border border-stone-800 rounded-2xl p-4 shadow-lg flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-rose-950 text-rose-400 flex items-center justify-center border border-rose-800">
            <Scale className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-stone-400 block">کل وزن گوشت و مرغ فروخته شده</span>
            <div className="text-base sm:text-lg font-bold text-rose-300 font-mono-digits">
              {formatWeight(totalWeightSoldKg)}
            </div>
          </div>
        </div>

        {/* Card 3: Invoices Count */}
        <div className="bg-stone-900 border border-stone-800 rounded-2xl p-4 shadow-lg flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-amber-950 text-amber-400 flex items-center justify-center border border-amber-800">
            <Receipt className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-stone-400 block">تعداد کل فاکتورها</span>
            <div className="text-base sm:text-lg font-bold text-amber-300 font-mono-digits">
              {toPersianDigits(invoices.length)} فاکتور
            </div>
          </div>
        </div>

        {/* Card 4: Average Ticket */}
        <div className="bg-stone-900 border border-stone-800 rounded-2xl p-4 shadow-lg flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-sky-950 text-sky-400 flex items-center justify-center border border-sky-800">
            <Banknote className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-stone-400 block">میانگین مبلغ هر فاکتور</span>
            <div className="text-base sm:text-lg font-bold text-sky-300 font-mono-digits">
              {formatCurrency(avgTicketRial, settings.currencyDisplayUnit)}
            </div>
          </div>
        </div>
      </div>

      {/* Main List Section */}
      <div className="bg-stone-900 border border-stone-800 rounded-2xl p-4 sm:p-5 shadow-xl">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <div className="relative flex-1 sm:w-72">
              <input
                type="text"
                placeholder="جستجوی شماره فاکتور، نام یا شماره تماس مشتری..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-stone-950 border border-stone-800 rounded-xl px-4 py-2 pr-9 text-xs text-stone-100 placeholder-stone-500 focus:outline-none focus:border-rose-600"
              />
              <Search className="w-4 h-4 text-stone-500 absolute right-3 top-2.5" />
            </div>

            {/* Payment Filter */}
            <select
              value={filterPayment}
              onChange={(e) => setFilterPayment(e.target.value)}
              className="bg-stone-950 border border-stone-800 rounded-xl px-3 py-2 text-xs text-stone-300 focus:outline-none focus:border-rose-600 cursor-pointer"
            >
              <option value="all">همه روش‌های پرداخت</option>
              <option value="card">کارتخوان (POS)</option>
              <option value="cash">نقدی</option>
              <option value="credit">نسیه</option>
            </select>
          </div>

          {invoices.length > 0 && (
            <button
              onClick={handleExportData}
              className="flex items-center gap-1.5 bg-stone-800 hover:bg-stone-700 text-stone-200 text-xs px-3 py-2 rounded-xl border border-stone-700 transition cursor-pointer self-end sm:self-auto"
            >
              <Download className="w-4 h-4 text-amber-400" />
              <span>پشتیبان‌گیری فاکتورها (JSON)</span>
            </button>
          )}
        </div>

        {/* Invoices Table */}
        <div className="overflow-x-auto">
          {filteredInvoices.length === 0 ? (
            <div className="py-16 text-center text-stone-500">
              <Receipt className="w-12 h-12 mx-auto mb-2 text-stone-600" />
              <p className="text-sm font-medium">هیچ فاکتوری یافت نشد</p>
              <p className="text-xs text-stone-600 mt-1">
                فاکتورهای صادرشده در بخش میز توزین به طور خودکار در این قسمت ثبت می‌گردند.
              </p>
            </div>
          ) : (
            <table className="w-full text-right text-xs">
              <thead>
                <tr className="border-b border-stone-800 text-stone-400 pb-2">
                  <th className="py-2.5 px-3">شماره فاکتور</th>
                  <th className="py-2.5 px-3">تاریخ و زمان</th>
                  <th className="py-2.5 px-3">مشتری</th>
                  <th className="py-2.5 px-3 text-center">تعداد قلم</th>
                  <th className="py-2.5 px-3 text-center">مجموع وزن (kg)</th>
                  <th className="py-2.5 px-3 text-center">پرداخت</th>
                  <th className="py-2.5 px-3 text-left">مبلغ نهایی</th>
                  <th className="py-2.5 px-3 text-center">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-800/60">
                {filteredInvoices.map((inv) => {
                  const invDate = new Date(inv.createdAt);
                  const dateStr = invDate.toLocaleDateString('fa-IR', {
                    year: 'numeric',
                    month: 'numeric',
                    day: 'numeric',
                    timeZone: 'Asia/Tehran',
                  });
                  const timeStr = invDate.toLocaleTimeString('fa-IR', {
                    hour: '2-digit',
                    minute: '2-digit',
                    timeZone: 'Asia/Tehran',
                  });

                  return (
                    <tr
                      key={inv.id}
                      className="hover:bg-stone-800/40 transition group"
                    >
                      <td className="py-3 px-3 font-mono font-bold text-amber-400 whitespace-nowrap">
                        {inv.invoiceNumber}
                      </td>
                      <td className="py-3 px-3 text-stone-300 font-mono-digits whitespace-nowrap">
                        <div>{dateStr}</div>
                        <div className="text-[10px] text-stone-500">{timeStr}</div>
                      </td>
                      <td className="py-3 px-3 text-stone-200">
                        {inv.customerName || <span className="text-stone-500">مشتری عمومی</span>}
                        {inv.customerPhone && (
                          <div className="text-[10px] text-stone-500 font-mono-digits">
                            {inv.customerPhone}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-3 text-center text-stone-300 font-mono-digits">
                        {toPersianDigits(inv.items.length)}
                      </td>
                      <td className="py-3 px-3 text-center font-bold text-emerald-400 font-mono-digits whitespace-nowrap">
                        {formatWeight(inv.totalWeightKg, { withUnit: false })}
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] ${
                          inv.paymentMethod === 'card'
                            ? 'bg-blue-950/80 text-blue-300 border border-blue-800/60'
                            : inv.paymentMethod === 'cash'
                            ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/60'
                            : 'bg-amber-950/80 text-amber-300 border border-amber-800/60'
                        }`}>
                          {inv.paymentMethod === 'card' ? 'کارتخوان' : inv.paymentMethod === 'cash' ? 'نقدی' : 'نسیه'}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-left font-bold text-sm text-stone-100 font-mono-digits whitespace-nowrap">
                        {formatCurrency(inv.finalAmountRial, settings.currencyDisplayUnit)}
                      </td>
                      <td className="py-3 px-3 text-center whitespace-nowrap">
                        <div className="flex items-center justify-center gap-1">
                          <button
                            onClick={() => onViewInvoice(inv)}
                            title="مشاهده و چاپ مجدد فاکتور"
                            className="p-1.5 bg-stone-800 hover:bg-emerald-900/60 text-stone-300 hover:text-emerald-300 rounded-lg transition cursor-pointer"
                          >
                            <Printer className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => {
                              if (confirm(`آیا از ابطال و حذف فاکتور ${inv.invoiceNumber} اطمینان دارید؟`)) {
                                onDeleteInvoice(inv.id);
                              }
                            }}
                            title="ابطال و حذف فاکتور"
                            className="p-1.5 bg-stone-800 hover:bg-rose-900/60 text-stone-400 hover:text-rose-300 rounded-lg transition cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};
