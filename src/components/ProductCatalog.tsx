import React, { useState, useMemo } from 'react';
import { Product, ProductCategory, ScaleReading, ShopSettings } from '../types';
import { formatCurrency, toPersianDigits, formatWeight } from '../services/currencyService';
import {
  Search,
  Plus,
  Scale,
  Sparkles,
  ShoppingBag,
  Check,
  Hash,
} from 'lucide-react';

interface ProductCatalogProps {
  products: Product[];
  scaleReading: ScaleReading;
  settings: ShopSettings;
  onAddItemToInvoice: (product: Product, weightKg: number) => void;
}

const CATEGORIES: { id: ProductCategory | 'all'; label: string; icon: string }[] = [
  { id: 'all', label: 'همه اقلام', icon: '🥩' },
  { id: 'chicken', label: 'مرغ و ماکیان', icon: '🍗' },
  { id: 'beef', label: 'گوشت گوساله', icon: '🥩' },
  { id: 'lamb', label: 'گوشت گوسفندی', icon: '🍖' },
  { id: 'minced', label: 'چرخ‌کرده', icon: '🍳' },
  { id: 'marinated', label: 'جوجه و مرینیت', icon: '🍢' },
  { id: 'other', label: 'اقلام جانبی', icon: '🥣' },
];

export const ProductCatalog: React.FC<ProductCatalogProps> = ({
  products,
  scaleReading,
  settings,
  onAddItemToInvoice,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<ProductCategory | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [manualWeightModalProduct, setManualWeightModalProduct] = useState<Product | null>(null);
  const [manualWeightInput, setManualWeightInput] = useState<string>('1.000');
  const [justAddedId, setJustAddedId] = useState<string | null>(null);

  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      const matchCategory = selectedCategory === 'all' || p.category === selectedCategory;
      const matchSearch =
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.code.includes(searchQuery);
      return matchCategory && matchSearch;
    });
  }, [products, selectedCategory, searchQuery]);

  const handleQuickAddCurrentScaleWeight = (product: Product) => {
    const net = scaleReading.netWeight;
    if (net <= 0.005) {
      // Scale is empty, open manual weight modal or prompt
      setManualWeightModalProduct(product);
      setManualWeightInput('1.000');
      return;
    }

    onAddItemToInvoice(product, net);
    setJustAddedId(product.id);
    setTimeout(() => setJustAddedId(null), 1200);
  };

  const handleConfirmManualWeight = (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualWeightModalProduct) return;
    const wt = parseFloat(manualWeightInput);
    if (!isNaN(wt) && wt > 0) {
      onAddItemToInvoice(manualWeightModalProduct, wt);
      setJustAddedId(manualWeightModalProduct.id);
      setManualWeightModalProduct(null);
      setTimeout(() => setJustAddedId(null), 1200);
    }
  };

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-2xl p-4 sm:p-5 shadow-xl flex flex-col h-full">
      {/* Search and Category Filters */}
      <div className="space-y-3 mb-4">
        {/* Search bar */}
        <div className="relative">
          <input
            type="text"
            placeholder="جستجوی نام گوشت یا کد کالا (مثلاً ۱۰۰۱ یا فیله)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-stone-950 border border-stone-800 rounded-xl px-4 py-2.5 pr-10 text-sm text-stone-100 placeholder-stone-500 focus:outline-none focus:border-rose-600 transition"
          />
          <Search className="w-4 h-4 text-stone-400 absolute right-3.5 top-3.5" />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute left-3 top-2.5 text-xs text-stone-400 hover:text-white bg-stone-800 px-2 py-0.5 rounded"
            >
              پاک کردن
            </button>
          )}
        </div>

        {/* Category Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
          {CATEGORIES.map((cat) => {
            const isSelected = selectedCategory === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition cursor-pointer whitespace-nowrap ${
                  isSelected
                    ? 'bg-rose-700 text-white shadow-md shadow-rose-900/40'
                    : 'bg-stone-800/80 text-stone-300 hover:bg-stone-800 hover:text-white border border-stone-800'
                }`}
              >
                <span>{cat.icon}</span>
                <span>{cat.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Live Scale Hint Banner */}
      <div className="bg-stone-950/70 border border-stone-800/80 rounded-xl p-2.5 mb-3 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <Scale className="w-4 h-4 text-emerald-400" />
          <span className="text-stone-300">وزن خالص روی باسکول:</span>
          <span className="text-emerald-400 font-bold font-mono-digits text-sm">
            {formatWeight(scaleReading.netWeight, { withUnit: true })}
          </span>
        </div>
        {scaleReading.netWeight > 0.005 ? (
          <span className="text-[11px] text-amber-300 bg-amber-950/60 border border-amber-800/60 px-2 py-0.5 rounded-md">
            کلیک روی هر کالا با وزن فوق ثبت می‌گردد
          </span>
        ) : (
          <span className="text-[11px] text-stone-400">
            برای ثبت خودکار، کالا را روی کفه ترازو بگذارید
          </span>
        )}
      </div>

      {/* Products Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 overflow-y-auto max-h-[500px] pr-1">
        {filteredProducts.length === 0 ? (
          <div className="col-span-full py-12 text-center text-stone-500">
            <ShoppingBag className="w-10 h-10 mx-auto mb-2 text-stone-600" />
            <p className="text-sm">کالایی با این مشخصات یافت نشد</p>
          </div>
        ) : (
          filteredProducts.map((product) => {
            const hasScaleWeight = scaleReading.netWeight > 0.005;
            const currentItemCostRial = Math.round(
              product.pricePerKgRial * (hasScaleWeight ? scaleReading.netWeight : 1)
            );
            const isJustAdded = justAddedId === product.id;

            return (
              <div
                key={product.id}
                className="bg-stone-950/90 border border-stone-800 hover:border-stone-700 rounded-xl p-3 flex flex-col justify-between transition hover:shadow-md relative group"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs bg-stone-900 border border-stone-800 text-stone-400 px-1.5 py-0.5 rounded font-mono-digits">
                        #{toPersianDigits(product.code)}
                      </span>
                      {product.isPopular && (
                        <span className="text-[10px] bg-amber-950 text-amber-400 border border-amber-800/80 px-1.5 py-0.2 rounded-full flex items-center gap-0.5">
                          <Sparkles className="w-2.5 h-2.5" /> پرفروش
                        </span>
                      )}
                    </div>
                  </div>

                  <h3 className="font-bold text-stone-100 text-sm leading-snug mb-1">
                    {product.name}
                  </h3>

                  <div className="flex items-baseline gap-1 text-xs text-stone-400 mb-2">
                    <span>قیمت پایه:</span>
                    <strong className="text-amber-400 font-bold font-mono-digits">
                      {formatCurrency(product.pricePerKgRial, settings.currencyDisplayUnit)}
                    </strong>
                    <span className="text-[11px] text-stone-500">
                      / {product.unit === 'kg' ? 'کیلوگرم' : 'بسته'}
                    </span>
                  </div>
                </div>

                {/* Bottom Action Area */}
                <div className="pt-2 border-t border-stone-800/70 flex items-center justify-between gap-2">
                  {/* Live calculated cost preview if scale has weight */}
                  {hasScaleWeight && (
                    <div className="text-[11px] text-emerald-400 font-mono-digits">
                      <span>مبلغ: </span>
                      <strong>
                        {formatCurrency(currentItemCostRial, settings.currencyDisplayUnit)}
                      </strong>
                    </div>
                  )}

                  <div className="flex items-center gap-1.5 mr-auto">
                    {/* Manual weight button */}
                    <button
                      onClick={() => {
                        setManualWeightModalProduct(product);
                        setManualWeightInput('1.000');
                      }}
                      title="ثبت با وزن دستی"
                      className="p-1.5 bg-stone-800 hover:bg-stone-700 text-stone-300 rounded-lg text-xs transition cursor-pointer"
                    >
                      <Hash className="w-3.5 h-3.5" />
                    </button>

                    {/* Primary Button */}
                    <button
                      onClick={() => handleQuickAddCurrentScaleWeight(product)}
                      disabled={isJustAdded}
                      className={`flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg transition cursor-pointer shadow-sm ${
                        isJustAdded
                          ? 'bg-emerald-600 text-white'
                          : hasScaleWeight
                          ? 'bg-rose-700 hover:bg-rose-600 text-white'
                          : 'bg-stone-800 hover:bg-stone-700 text-stone-200'
                      }`}
                    >
                      {isJustAdded ? (
                        <>
                          <Check className="w-3.5 h-3.5" />
                          <span>افزوده شد</span>
                        </>
                      ) : hasScaleWeight ? (
                        <>
                          <Scale className="w-3.5 h-3.5" />
                          <span>توزین و افزودن</span>
                        </>
                      ) : (
                        <>
                          <Plus className="w-3.5 h-3.5" />
                          <span>افزودن</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Manual Weight Modal */}
      {manualWeightModalProduct && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5 max-w-sm w-full shadow-2xl">
            <h4 className="font-bold text-white text-base mb-1">
              ثبت وزن دستی: {manualWeightModalProduct.name}
            </h4>
            <p className="text-xs text-stone-400 mb-4">
              نرخ: {formatCurrency(manualWeightModalProduct.pricePerKgRial, settings.currencyDisplayUnit)} به ازای هر کیلوگرم
            </p>

            <form onSubmit={handleConfirmManualWeight} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-stone-300 mb-1.5">
                  مقدار وزن (کیلوگرم):
                </label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.005"
                    min="0.01"
                    max="100"
                    autoFocus
                    value={manualWeightInput}
                    onChange={(e) => setManualWeightInput(e.target.value)}
                    className="w-full bg-stone-950 border border-stone-700 rounded-xl px-4 py-2.5 text-base text-white text-left font-mono-digits focus:outline-none focus:border-rose-500"
                    dir="ltr"
                  />
                  <span className="absolute left-3 top-3 text-xs text-stone-400">
                    kg
                  </span>
                </div>
              </div>

              {/* Quick weight buttons */}
              <div className="grid grid-cols-4 gap-1.5 text-xs">
                {['0.250', '0.500', '1.000', '1.500'].map((w) => (
                  <button
                    type="button"
                    key={w}
                    onClick={() => setManualWeightInput(w)}
                    className="bg-stone-800 hover:bg-stone-700 text-stone-200 py-1.5 rounded-lg font-mono-digits"
                  >
                    {toPersianDigits(w)} kg
                  </button>
                ))}
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-stone-800">
                <button
                  type="button"
                  onClick={() => setManualWeightModalProduct(null)}
                  className="px-4 py-2 rounded-xl text-xs text-stone-400 hover:text-white transition"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl text-xs bg-rose-700 hover:bg-rose-600 text-white font-bold transition shadow-md"
                >
                  افزودن به فاکتور
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
