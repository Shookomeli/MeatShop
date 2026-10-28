import React, { useState } from 'react';
import { ScaleReading, ShopSettings } from '../types';
import { toPersianDigits } from '../services/currencyService';
import {
  Scale,
  RotateCcw,
  MinusCircle,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Radio,
  Trash2,
} from 'lucide-react';

interface ScaleDisplayProps {
  scaleReading: ScaleReading;
  settings: ShopSettings;
  onZero: () => void;
  onTare: () => void;
  onClearTare: () => void;
  onSetWeight: (weightKg: number) => void;
}

export const ScaleDisplay: React.FC<ScaleDisplayProps> = ({
  scaleReading,
  settings,
  onZero,
  onTare,
  onClearTare,
  onSetWeight,
}) => {
  const [customWeightInput, setCustomWeightInput] = useState<string>('');
  const [showSimControls, setShowSimControls] = useState<boolean>(true);
  const [viewMode, setViewMode] = useState<'net' | 'gross'>('net');

  const handleApplyCustomWeight = (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseFloat(customWeightInput);
    if (!isNaN(val) && val >= 0) {
      onSetWeight(val);
      setCustomWeightInput('');
    }
  };

  const handleQuickAddWeight = (incrementKg: number) => {
    const current = scaleReading.grossWeight;
    const next = Math.max(0, current + incrementKg);
    onSetWeight(next);
  };

  const displayedWeight = viewMode === 'net' ? scaleReading.netWeight : scaleReading.grossWeight;
  const isNetActive = scaleReading.tareWeight > 0.001;

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-2xl p-4 sm:p-5 shadow-xl relative overflow-hidden">
      {/* Indicator Brand & Model Bar */}
      <div className="flex items-center justify-between border-b border-stone-800 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <div className="bg-emerald-950 text-emerald-400 p-1.5 rounded-lg border border-emerald-800/80">
            <Scale className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-white text-sm tracking-wider font-mono">
                KELI XK3118T1
              </span>
              <span className="text-[11px] bg-stone-800 text-stone-300 px-2 py-0.5 rounded border border-stone-700">
                {settings.scaleMode === 'keli_xk3118t1' ? 'حالت پورت سریال RS232' : 'شبیه‌ساز هوشمند کفه'}
              </span>
            </div>
            <span className="text-[11px] text-stone-400">
              دقت: ۱ گرم | حداکثر ظرفیت: ۵۰ کیلوگرم | خروجی استاندارد پیوسته
            </span>
          </div>
        </div>

        {/* View Gross / Net Switcher */}
        <div className="flex items-center bg-stone-950 p-1 rounded-lg border border-stone-800 text-xs">
          <button
            onClick={() => setViewMode('net')}
            className={`px-2.5 py-1 rounded-md transition cursor-pointer font-medium ${
              viewMode === 'net'
                ? 'bg-emerald-600 text-white font-bold shadow-sm'
                : 'text-stone-400 hover:text-white'
            }`}
          >
            وزن خالص (NET)
          </button>
          <button
            onClick={() => setViewMode('gross')}
            className={`px-2.5 py-1 rounded-md transition cursor-pointer font-medium ${
              viewMode === 'gross'
                ? 'bg-amber-600 text-white font-bold shadow-sm'
                : 'text-stone-400 hover:text-white'
            }`}
          >
            وزن ناخالص (GROSS)
          </button>
        </div>
      </div>

      {/* Main Digital LED Display Panel (Resembles industrial KELI electronic scale) */}
      <div className="bg-black/90 border-2 border-stone-700 rounded-xl p-4 sm:p-6 shadow-inner relative flex flex-col justify-between mb-4">
        {/* Annunciator Indicator LEDs Row */}
        <div className="flex items-center justify-between border-b border-stone-900 pb-2 mb-2 text-[11px]">
          {/* Stable LED */}
          <div className="flex items-center gap-1.5">
            <span
              className={`w-2.5 h-2.5 rounded-full transition ${
                scaleReading.isStable && scaleReading.isConnected
                  ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]'
                  : 'bg-stone-800'
              }`}
            />
            <span
              className={`font-mono uppercase font-bold ${
                scaleReading.isStable && scaleReading.isConnected
                  ? 'text-emerald-400'
                  : 'text-stone-600'
              }`}
            >
              STABLE (ثابت)
            </span>
          </div>

          {/* Zero LED */}
          <div className="flex items-center gap-1.5">
            <span
              className={`w-2.5 h-2.5 rounded-full transition ${
                scaleReading.isZero
                  ? 'bg-amber-400 shadow-[0_0_8px_#fbbf24]'
                  : 'bg-stone-800'
              }`}
            />
            <span
              className={`font-mono uppercase font-bold ${
                scaleReading.isZero ? 'text-amber-400' : 'text-stone-600'
              }`}
            >
              ZERO (مرکز صفر)
            </span>
          </div>

          {/* Tare LED */}
          <div className="flex items-center gap-1.5">
            <span
              className={`w-2.5 h-2.5 rounded-full transition ${
                isNetActive
                  ? 'bg-sky-400 shadow-[0_0_8px_#38bdf8]'
                  : 'bg-stone-800'
              }`}
            />
            <span
              className={`font-mono uppercase font-bold ${
                isNetActive ? 'text-sky-400' : 'text-stone-600'
              }`}
            >
              TARE (پارسنگ فعال)
            </span>
          </div>

          {/* Mode Indicator */}
          <div className="flex items-center gap-1 text-stone-400 font-mono text-[10px]">
            <Radio className="w-3 h-3 text-stone-500" />
            <span>{viewMode === 'net' ? 'NET MODE' : 'GROSS MODE'}</span>
          </div>
        </div>

        {/* Big LED Digits Display */}
        <div className="flex items-baseline justify-between py-2 sm:py-4 px-2">
          {/* Status badge in corner */}
          <div className="flex flex-col gap-1 text-xs">
            <span className="text-stone-500 font-mono text-[11px]">
              پارسنگ (Tare):{' '}
              <strong className="text-sky-400 font-bold font-mono-digits">
                {toPersianDigits(scaleReading.tareWeight.toFixed(3))}
              </strong>{' '}
              kg
            </span>
            <span className="text-stone-500 font-mono text-[11px]">
              ناخالص (Gross):{' '}
              <strong className="text-stone-300 font-bold font-mono-digits">
                {toPersianDigits(scaleReading.grossWeight.toFixed(3))}
              </strong>{' '}
              kg
            </span>
          </div>

          {/* The Big Digits */}
          <div className="flex items-baseline gap-2 direction-ltr">
            <div
              className={`text-4xl sm:text-6xl lg:text-7xl font-bold font-mono-digits scale-led-display transition-colors ${
                !scaleReading.isConnected
                  ? 'text-rose-500 scale-led-display-red'
                  : !scaleReading.isStable
                  ? 'text-amber-400'
                  : 'text-emerald-400'
              }`}
            >
              {!scaleReading.isConnected
                ? 'OFFLINE'
                : displayedWeight.toFixed(3)}
            </div>
            <span className="text-xl sm:text-2xl font-bold text-emerald-500 font-mono">
              kg
            </span>
          </div>
        </div>

        {/* Error / Alert banner if any */}
        {scaleReading.errorMessage && (
          <div className="bg-rose-950/80 border border-rose-800/80 text-rose-300 text-xs px-3 py-1.5 rounded-lg flex items-center gap-2 mt-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{scaleReading.errorMessage}</span>
          </div>
        )}
      </div>

      {/* Industrial Scale Hardware Control Buttons (ZERO, TARE, CLEAR TARE) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
        {/* Zero Button */}
        <button
          onClick={onZero}
          title="صفر کردن کفه ترازو وقتی کالا روی آن نیست"
          className="flex items-center justify-center gap-2 bg-stone-800 hover:bg-stone-700 active:scale-95 text-stone-100 py-2.5 px-3 rounded-xl border border-stone-700 transition cursor-pointer font-medium text-xs sm:text-sm shadow-sm"
        >
          <RotateCcw className="w-4 h-4 text-amber-400" />
          <span>صفر کفه (ZERO)</span>
        </button>

        {/* Tare Button */}
        <button
          onClick={onTare}
          title="پارسنگ: وزن ظرف یا سینی روی کفه را صفر می‌کند تا فقط وزن گوشت محاسبه شود"
          className="flex items-center justify-center gap-2 bg-sky-950/70 hover:bg-sky-900/80 active:scale-95 text-sky-200 py-2.5 px-3 rounded-xl border border-sky-800 transition cursor-pointer font-medium text-xs sm:text-sm shadow-sm"
        >
          <MinusCircle className="w-4 h-4 text-sky-400" />
          <span>پارسنگ ظرف (TARE)</span>
        </button>

        {/* Clear Tare Button */}
        <button
          onClick={onClearTare}
          disabled={!isNetActive}
          title="حذف پارسنگ و بازگشت به وزن کل"
          className="flex items-center justify-center gap-2 bg-stone-800 hover:bg-stone-700 disabled:opacity-40 disabled:hover:bg-stone-800 active:scale-95 text-stone-300 py-2.5 px-3 rounded-xl border border-stone-700 transition cursor-pointer font-medium text-xs sm:text-sm shadow-sm"
        >
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>حذف پارسنگ</span>
        </button>

        {/* Remove All Platter Weight */}
        <button
          onClick={() => onSetWeight(0)}
          title="برداشتن بار از روی کفه ترازو"
          className="flex items-center justify-center gap-2 bg-rose-950/60 hover:bg-rose-900/70 active:scale-95 text-rose-300 py-2.5 px-3 rounded-xl border border-rose-800 transition cursor-pointer font-medium text-xs sm:text-sm shadow-sm"
        >
          <Trash2 className="w-4 h-4 text-rose-400" />
          <span>تخلیه کفه (خالی)</span>
        </button>
      </div>

      {/* Simulator Quick Weight Platter Tools */}
      <div className="bg-stone-950/60 border border-stone-800/80 rounded-xl p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-amber-400" />
            <span className="text-xs font-bold text-stone-200">
              قراردادن بار روی کفه ترازو (شبیه‌ساز باسکول):
            </span>
          </div>
          <button
            onClick={() => setShowSimControls(!showSimControls)}
            className="text-[11px] text-stone-400 hover:text-white"
          >
            {showSimControls ? 'کوچک‌نمایی' : 'نمایش'}
          </button>
        </div>

        {showSimControls && (
          <div className="space-y-2.5">
            {/* Quick weight chips */}
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-stone-400 ml-1">افزودن سریع:</span>
              {[
                { label: 'سینی خالی (۱۲۰ گرم)', val: 0.12 },
                { label: '+۲۵۰ گرم', val: 0.25 },
                { label: '+۵۰۰ گرم', val: 0.5 },
                { label: '+۱ کیلوگرم', val: 1.0 },
                { label: '+۱.۵ کیلوگرم', val: 1.5 },
                { label: '+۲.۴ کیلوگرم', val: 2.4 },
                { label: '+۳.۲ کیلوگرم', val: 3.2 },
              ].map((chip) => (
                <button
                  key={chip.label}
                  onClick={() => handleQuickAddWeight(chip.val)}
                  className="bg-stone-800/90 hover:bg-stone-700 active:scale-95 text-stone-200 text-xs px-2.5 py-1 rounded-lg border border-stone-700 transition cursor-pointer font-mono-digits"
                >
                  {toPersianDigits(chip.label)}
                </button>
              ))}
            </div>

            {/* Direct exact weight form */}
            <form onSubmit={handleApplyCustomWeight} className="flex items-center gap-2 pt-1">
              <span className="text-xs text-stone-400">تنظیم دقیق وزن:</span>
              <div className="relative flex-1 max-w-xs">
                <input
                  type="number"
                  step="0.001"
                  min="0"
                  max="50"
                  placeholder="مثلاً ۱.۷۵۰"
                  value={customWeightInput}
                  onChange={(e) => setCustomWeightInput(e.target.value)}
                  className="w-full bg-stone-900 border border-stone-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-stone-500 focus:outline-none focus:border-rose-500 font-mono-digits text-left"
                  dir="ltr"
                />
                <span className="absolute left-2 top-1.5 text-xs text-stone-500 font-mono">
                  kg
                </span>
              </div>
              <button
                type="submit"
                className="bg-emerald-700 hover:bg-emerald-600 text-white text-xs px-3 py-1.5 rounded-lg font-medium transition cursor-pointer"
              >
                اعمال وزن روی کفه
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};
