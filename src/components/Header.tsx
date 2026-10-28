import React, { useEffect, useState } from 'react';
import { ScaleReading, ShopSettings } from '../types';
import { toPersianDigits } from '../services/currencyService';
import {
  Receipt,
  History,
  Package,
  Settings,
  CircleDot,
  Coins,
  RefreshCw
} from 'lucide-react';

interface HeaderProps {
  currentTab: 'pos' | 'history' | 'products' | 'settings';
  setCurrentTab: (tab: 'pos' | 'history' | 'products' | 'settings') => void;
  scaleReading: ScaleReading;
  settings: ShopSettings;
  onToggleCurrency: () => void;
  onReconnectScale: () => void;
  invoicesCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  currentTab,
  setCurrentTab,
  scaleReading,
  settings,
  onToggleCurrency,
  onReconnectScale,
  invoicesCount,
}) => {
  const [tehranTime, setTehranTime] = useState<string>('');
  const [persianDate, setPersianDate] = useState<string>('');

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      // Format time in Tehran time zone
      const timeStr = now.toLocaleTimeString('fa-IR', {
        timeZone: 'Asia/Tehran',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
      // Format date in Shamsi / Persian calendar
      const dateStr = now.toLocaleDateString('fa-IR', {
        timeZone: 'Asia/Tehran',
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
      setTehranTime(timeStr);
      setPersianDate(dateStr);
    };

    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="bg-stone-900 border-b border-stone-800 sticky top-0 z-40 shadow-lg">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 sm:h-20">
          {/* Logo & Shop Title */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-gradient-to-br from-rose-700 to-amber-600 flex items-center justify-center text-white shadow-md shadow-rose-900/40">
              <span className="text-xl sm:text-2xl">🥩</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base sm:text-lg font-bold text-white tracking-tight">
                  {settings.shopName}
                </h1>
                <span className="text-xs bg-rose-950/80 text-rose-300 border border-rose-800/60 px-2 py-0.5 rounded-full font-mono-digits">
                  نسخه ۲.۰
                </span>
              </div>
              <p className="text-xs text-stone-400 hidden sm:block">
                سیستم توزین هوشمند و صدور فاکتور متصل به نشان‌دهنده KELI XK3118T1
              </p>
            </div>
          </div>

          {/* Center Info: Live Tehran Time & Persian Date */}
          <div className="hidden md:flex flex-col items-center bg-stone-950/80 px-4 py-1.5 rounded-lg border border-stone-800">
            <span className="text-xs text-amber-400 font-medium">{persianDate}</span>
            <div className="flex items-center gap-2 text-stone-300 text-sm font-bold font-mono-digits">
              <span>ساعت:</span>
              <span className="text-white">{tehranTime}</span>
              <span className="text-[10px] text-stone-500 font-normal">تهران</span>
            </div>
          </div>

          {/* Right Controls: Scale Status, Currency Toggle & Action buttons */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Currency Unit Toggle Button */}
            <button
              onClick={onToggleCurrency}
              title="تغییر واحد نمایش ارز بین تومان و ریال (در دیتابیس همواره ریال ذخیره می‌شود)"
              className="flex items-center gap-1.5 bg-stone-800 hover:bg-stone-700 active:scale-95 text-stone-200 px-2.5 sm:px-3 py-1.5 rounded-lg border border-stone-700 transition cursor-pointer text-xs sm:text-sm font-medium shadow-sm"
            >
              <Coins className="w-4 h-4 text-amber-400" />
              <span className="hidden sm:inline">واحد نمایش:</span>
              <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${
                settings.currencyDisplayUnit === 'TOMAN'
                  ? 'bg-amber-500 text-stone-950'
                  : 'bg-emerald-600 text-white'
              }`}>
                {settings.currencyDisplayUnit === 'TOMAN' ? 'تومان' : 'ریال'}
              </span>
            </button>

            {/* Scale Hardware Status Badge */}
            <div
              className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg border text-xs sm:text-sm font-medium transition ${
                !scaleReading.isConnected
                  ? 'bg-rose-950/70 border-rose-800 text-rose-300'
                  : !scaleReading.isStable
                  ? 'bg-amber-950/70 border-amber-800 text-amber-300'
                  : 'bg-emerald-950/70 border-emerald-800 text-emerald-300'
              }`}
              title={
                !scaleReading.isConnected
                  ? 'ترازو قطع است - کلیک جهت اتصال مجدد'
                  : !scaleReading.isStable
                  ? 'ترازو در حال پایدار شدن'
                  : 'ترازو متصل و پایدار'
              }
            >
              <CircleDot
                className={`w-3.5 h-3.5 ${
                  !scaleReading.isConnected
                    ? 'text-rose-500 animate-pulse'
                    : !scaleReading.isStable
                    ? 'text-amber-400 animate-spin'
                    : 'text-emerald-400'
                }`}
              />
              <span className="hidden sm:inline">
                {settings.scaleMode === 'keli_xk3118t1' ? 'ترازو KELI' : 'ترازو شبیه‌ساز'}:
              </span>
              <span className="font-bold">
                {!scaleReading.isConnected
                  ? 'قطع'
                  : !scaleReading.isStable
                  ? 'ناپایدار'
                  : 'متصل'}
              </span>
              {!scaleReading.isConnected && (
                <button
                  onClick={onReconnectScale}
                  className="hover:text-white p-0.5"
                  title="اتصال مجدد"
                >
                  <RefreshCw className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto pb-2 pt-1 border-t border-stone-800/80 no-scrollbar">
          <button
            onClick={() => setCurrentTab('pos')}
            className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition cursor-pointer whitespace-nowrap ${
              currentTab === 'pos'
                ? 'bg-rose-700 text-white shadow-md shadow-rose-900/50'
                : 'text-stone-300 hover:bg-stone-800 hover:text-white'
            }`}
          >
            <Receipt className="w-4 h-4" />
            <span>میز توزین و صدور فاکتور</span>
          </button>

          <button
            onClick={() => setCurrentTab('history')}
            className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition cursor-pointer whitespace-nowrap ${
              currentTab === 'history'
                ? 'bg-rose-700 text-white shadow-md shadow-rose-900/50'
                : 'text-stone-300 hover:bg-stone-800 hover:text-white'
            }`}
          >
            <History className="w-4 h-4" />
            <span>تاریخچه فاکتورها</span>
            {invoicesCount > 0 && (
              <span className="bg-stone-800 text-amber-300 px-1.5 py-0.2 rounded-full text-[11px] font-mono-digits font-bold">
                {toPersianDigits(invoicesCount)}
              </span>
            )}
          </button>

          <button
            onClick={() => setCurrentTab('products')}
            className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition cursor-pointer whitespace-nowrap ${
              currentTab === 'products'
                ? 'bg-rose-700 text-white shadow-md shadow-rose-900/50'
                : 'text-stone-300 hover:bg-stone-800 hover:text-white'
            }`}
          >
            <Package className="w-4 h-4" />
            <span>مدیریت کالاها و نرخ‌نامه</span>
          </button>

          <button
            onClick={() => setCurrentTab('settings')}
            className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition cursor-pointer whitespace-nowrap ${
              currentTab === 'settings'
                ? 'bg-rose-700 text-white shadow-md shadow-rose-900/50'
                : 'text-stone-300 hover:bg-stone-800 hover:text-white'
            }`}
          >
            <Settings className="w-4 h-4" />
            <span>تنظیمات ترازو و فروشگاه</span>
          </button>
        </div>
      </div>
    </header>
  );
};
