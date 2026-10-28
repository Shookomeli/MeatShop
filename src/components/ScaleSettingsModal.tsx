import React, { useState } from 'react';
import { ShopSettings } from '../types';
import {
  Settings,
  Coins,
  Store,
  Save,
  RotateCcw,
  CheckCircle2,
  Cpu,
} from 'lucide-react';
import { DEFAULT_SETTINGS } from '../services/storageService';

interface ScaleSettingsProps {
  settings: ShopSettings;
  onSaveSettings: (settings: ShopSettings) => void;
  onSimulateError: (type: 'disconnect' | 'unstable' | 'clear') => void;
}

export const ScaleSettingsView: React.FC<ScaleSettingsProps> = ({
  settings,
  onSaveSettings,
  onSimulateError,
}) => {
  const [formData, setFormData] = useState<ShopSettings>({ ...settings });
  const [savedSuccess, setSavedSuccess] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSaveSettings(formData);
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 2000);
  };

  const handleReset = () => {
    if (confirm('آیا مایلید تمام تنظیمات به مقادیر اولیه بازگردانی شوند؟')) {
      setFormData(DEFAULT_SETTINGS);
      onSaveSettings(DEFAULT_SETTINGS);
    }
  };

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-2xl p-4 sm:p-6 shadow-xl max-w-4xl mx-auto">
      <div className="flex items-center justify-between border-b border-stone-800 pb-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="bg-rose-950 text-rose-400 p-2 rounded-xl border border-rose-800">
            <Settings className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">تنظیمات سیستم و پیکربندی سخت‌افزار ترازو</h2>
            <p className="text-xs text-stone-400">
              مدیریت ارتباط نشان‌دهنده KELI XK3118T1، واحد پولی، و مشخصات فروشگاه
            </p>
          </div>
        </div>

        {savedSuccess && (
          <div className="flex items-center gap-1.5 bg-emerald-950 text-emerald-300 border border-emerald-800 px-3 py-1.5 rounded-xl text-xs font-bold animate-fadeIn">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>تنظیمات ذخیره شد</span>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="space-y-6 text-xs">
        {/* Section 1: Currency & Accounting */}
        <div className="bg-stone-950/70 border border-stone-800 rounded-xl p-4">
          <h3 className="font-bold text-stone-200 text-sm mb-3 flex items-center gap-2">
            <Coins className="w-4 h-4 text-amber-400" />
            <span>تنظیمات حسابداری و واحد نمایش ارز (Currency Note)</span>
          </h3>

          <div className="space-y-3">
            <div>
              <label className="block text-stone-300 mb-2 font-medium">
                واحد پیش‌فرض نمایش مبالغ در سیستم:
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label
                  className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition ${
                    formData.currencyDisplayUnit === 'TOMAN'
                      ? 'bg-amber-950/30 border-amber-600/80 text-white'
                      : 'bg-stone-900 border-stone-800 text-stone-400 hover:border-stone-700'
                  }`}
                >
                  <input
                    type="radio"
                    name="currencyDisplayUnit"
                    checked={formData.currencyDisplayUnit === 'TOMAN'}
                    onChange={() =>
                      setFormData({ ...formData, currencyDisplayUnit: 'TOMAN' })
                    }
                    className="mt-1"
                  />
                  <div>
                    <span className="font-bold text-amber-400 block text-sm">
                      تومان (پیش‌فرض ایران)
                    </span>
                    <span className="text-[11px] text-stone-400 leading-normal">
                      مبالغ فاکتورها و اتیکت‌های کالا به تومان نمایش داده می‌شوند (هر تومان = ۱۰ ریال).
                    </span>
                  </div>
                </label>

                <label
                  className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition ${
                    formData.currencyDisplayUnit === 'RIAL'
                      ? 'bg-emerald-950/30 border-emerald-600/80 text-white'
                      : 'bg-stone-900 border-stone-800 text-stone-400 hover:border-stone-700'
                  }`}
                >
                  <input
                    type="radio"
                    name="currencyDisplayUnit"
                    checked={formData.currencyDisplayUnit === 'RIAL'}
                    onChange={() =>
                      setFormData({ ...formData, currencyDisplayUnit: 'RIAL' })
                    }
                    className="mt-1"
                  />
                  <div>
                    <span className="font-bold text-emerald-400 block text-sm">
                      ریال (واحد حسابداری رسمی)
                    </span>
                    <span className="text-[11px] text-stone-400 leading-normal">
                      مبالغ به ریال نمایش داده می‌شوند. در پایگاه داده کلیه سوابق همیشه بر حسب ریال ذخیره می‌شوند.
                    </span>
                  </div>
                </label>
              </div>
            </div>

            <div className="bg-stone-900 border border-stone-800 p-2.5 rounded-lg text-stone-400 text-[11px] leading-relaxed">
              💡 <strong>قانون پایگاه داده:</strong> تمام داده‌های مالی همواره به صورت عدد صحیح ریال ذخیره می‌شوند. تغییر واحد نمایش تاثیری در یکپارچگی داده‌های تاریخی ندارد.
            </div>
          </div>
        </div>

        {/* Section 2: Hardware Scale Configuration */}
        <div className="bg-stone-950/70 border border-stone-800 rounded-xl p-4">
          <h3 className="font-bold text-stone-200 text-sm mb-3 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-emerald-400" />
            <span>پیکربندی اتصال ترازو و باسکول (SCALE_MODE)</span>
          </h3>

          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label
                className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition ${
                  formData.scaleMode === 'mock'
                    ? 'bg-stone-900 border-emerald-600 text-white'
                    : 'bg-stone-900 border-stone-800 text-stone-400 hover:border-stone-700'
                }`}
              >
                <input
                  type="radio"
                  name="scaleMode"
                  checked={formData.scaleMode === 'mock'}
                  onChange={() => setFormData({ ...formData, scaleMode: 'mock' })}
                  className="mt-1"
                />
                <div>
                  <span className="font-bold text-emerald-400 block text-sm">
                    شبیه‌ساز هوشمند کفه (mock)
                  </span>
                  <span className="text-[11px] text-stone-400">
                    مناسب محیط توسعه، آموزش پرسنل و تست بدون اتصال فیزیکی به کابل RS232.
                  </span>
                </div>
              </label>

              <label
                className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition ${
                  formData.scaleMode === 'keli_xk3118t1'
                    ? 'bg-stone-900 border-emerald-600 text-white'
                    : 'bg-stone-900 border-stone-800 text-stone-400 hover:border-stone-700'
                }`}
              >
                <input
                  type="radio"
                  name="scaleMode"
                  checked={formData.scaleMode === 'keli_xk3118t1'}
                  onChange={() =>
                    setFormData({ ...formData, scaleMode: 'keli_xk3118t1' })
                  }
                  className="mt-1"
                />
                <div>
                  <span className="font-bold text-emerald-400 block text-sm">
                    ارتباط زنده با نشان‌دهنده KELI XK3118T1
                  </span>
                  <span className="text-[11px] text-stone-400">
                    خواندن مستقیم رشته پیوسته ASCII از پورت سریال RS232 / USB COM.
                  </span>
                </div>
              </label>
            </div>

            {/* Serial Parameters */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-stone-900/60 p-3 rounded-lg border border-stone-800/80">
              <div>
                <label className="block text-stone-400 mb-1">پورت سریال (COM Port):</label>
                <input
                  type="text"
                  value={formData.comPort}
                  onChange={(e) => setFormData({ ...formData, comPort: e.target.value })}
                  className="w-full bg-stone-950 border border-stone-800 rounded px-2.5 py-1.5 text-white font-mono text-left"
                  dir="ltr"
                />
              </div>

              <div>
                <label className="block text-stone-400 mb-1">نرخ باود (Baud Rate):</label>
                <select
                  value={formData.baudRate}
                  onChange={(e) =>
                    setFormData({ ...formData, baudRate: parseInt(e.target.value) })
                  }
                  className="w-full bg-stone-950 border border-stone-800 rounded px-2.5 py-1.5 text-white font-mono text-left"
                  dir="ltr"
                >
                  <option value="9600">9600 (پیش‌فرض KELI)</option>
                  <option value="4800">4800</option>
                  <option value="2400">2400</option>
                  <option value="1200">1200</option>
                </select>
              </div>

              <div>
                <label className="block text-stone-400 mb-1">پروتکل ارتباطی:</label>
                <input
                  type="text"
                  disabled
                  value="8-N-1 Continuous (ASCII)"
                  className="w-full bg-stone-950/50 border border-stone-800 rounded px-2.5 py-1.5 text-stone-500 font-mono text-left"
                  dir="ltr"
                />
              </div>
            </div>

            {/* Hardware Test / Error Injection (for testing edge cases) */}
            <div className="border-t border-stone-800/80 pt-3">
              <span className="text-stone-400 text-xs font-bold block mb-2">
                تست خطاهای احتمالی سخت‌افزار ترازو (Error States):
              </span>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => onSimulateError('unstable')}
                  className="bg-stone-800 hover:bg-stone-700 text-amber-400 px-3 py-1.5 rounded-lg border border-stone-700"
                >
                  شبیه‌سازی لرزش و ناپایداری بار (UnstableWeightError)
                </button>
                <button
                  type="button"
                  onClick={() => onSimulateError('disconnect')}
                  className="bg-stone-800 hover:bg-stone-700 text-rose-400 px-3 py-1.5 rounded-lg border border-stone-700"
                >
                  شبیه‌سازی قطعی کابل پورت (ScaleUnavailableError)
                </button>
                <button
                  type="button"
                  onClick={() => onSimulateError('clear')}
                  className="bg-emerald-950 hover:bg-emerald-900 text-emerald-300 px-3 py-1.5 rounded-lg border border-emerald-800"
                >
                  وضعیت عادی (رفع خطا)
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Section 3: Shop Information & Receipt Customization */}
        <div className="bg-stone-950/70 border border-stone-800 rounded-xl p-4">
          <h3 className="font-bold text-stone-200 text-sm mb-3 flex items-center gap-2">
            <Store className="w-4 h-4 text-rose-400" />
            <span>مشخصات فروشگاه و سربرگ رسید چاپی</span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
            <div>
              <label className="block text-stone-300 mb-1 font-medium">نام فروشگاه:</label>
              <input
                type="text"
                required
                value={formData.shopName}
                onChange={(e) => setFormData({ ...formData, shopName: e.target.value })}
                className="w-full bg-stone-900 border border-stone-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-rose-500"
              />
            </div>

            <div>
              <label className="block text-stone-300 mb-1 font-medium">شعار یا صنف:</label>
              <input
                type="text"
                value={formData.tagline}
                onChange={(e) => setFormData({ ...formData, tagline: e.target.value })}
                className="w-full bg-stone-900 border border-stone-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-rose-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
            <div>
              <label className="block text-stone-300 mb-1 font-medium">شماره تلفن تماس:</label>
              <input
                type="text"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="w-full bg-stone-900 border border-stone-800 rounded-lg px-3 py-2 text-white font-mono-digits"
                dir="ltr"
              />
            </div>

            <div>
              <label className="block text-stone-300 mb-1 font-medium">درصد مالیات بر ارزش افزوده (اختیاری):</label>
              <input
                type="number"
                min="0"
                max="30"
                value={formData.taxPercent}
                onChange={(e) =>
                  setFormData({ ...formData, taxPercent: parseFloat(e.target.value) || 0 })
                }
                className="w-full bg-stone-900 border border-stone-800 rounded-lg px-3 py-2 text-white font-mono-digits text-left"
                dir="ltr"
              />
            </div>
          </div>

          <div className="mb-3">
            <label className="block text-stone-300 mb-1 font-medium">آدرس فروشگاه:</label>
            <input
              type="text"
              value={formData.address}
              onChange={(e) => setFormData({ ...formData, address: e.target.value })}
              className="w-full bg-stone-900 border border-stone-800 rounded-lg px-3 py-2 text-white"
            />
          </div>

          <div>
            <label className="block text-stone-300 mb-1 font-medium">متن پیام انتهای فاکتور:</label>
            <textarea
              rows={2}
              value={formData.receiptFooter}
              onChange={(e) =>
                setFormData({ ...formData, receiptFooter: e.target.value })
              }
              className="w-full bg-stone-900 border border-stone-800 rounded-lg px-3 py-2 text-white resize-none"
            />
          </div>
        </div>

        {/* Buttons */}
        <div className="flex items-center justify-between pt-2">
          <button
            type="button"
            onClick={handleReset}
            className="flex items-center gap-1.5 text-stone-400 hover:text-white px-3 py-2 rounded-xl hover:bg-stone-800 transition cursor-pointer"
          >
            <RotateCcw className="w-4 h-4" />
            <span>بازگردانی پیش‌فرض‌ها</span>
          </button>

          <button
            type="submit"
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-sm px-6 py-2.5 rounded-xl shadow-lg transition cursor-pointer"
          >
            <Save className="w-4 h-4" />
            <span>ذخیره کلیه تنظیمات</span>
          </button>
        </div>
      </form>
    </div>
  );
};
