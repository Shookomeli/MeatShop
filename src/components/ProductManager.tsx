import React, { useState } from 'react';
import { Product, ProductCategory, ShopSettings } from '../types';
import {
  formatCurrency,
  toPersianDigits,
  rialToToman,
  tomanToRial,
} from '../services/currencyService';
import {
  Plus,
  Edit2,
  Trash2,
  Check,
  X,
  Sparkles,
  Package,
  Search,
  RotateCcw,
} from 'lucide-react';
import { DEFAULT_PRODUCTS } from '../services/storageService';

interface ProductManagerProps {
  products: Product[];
  settings: ShopSettings;
  onUpdateProducts: (products: Product[]) => void;
}

export const ProductManager: React.FC<ProductManagerProps> = ({
  products,
  settings,
  onUpdateProducts,
}) => {
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editPriceInput, setEditPriceInput] = useState<string>('');
  const [showAddModal, setShowAddModal] = useState(false);

  // New product form
  const [newName, setNewName] = useState('');
  const [newCode, setNewCode] = useState('');
  const [newCategory, setNewCategory] = useState<ProductCategory>('beef');
  const [newPriceInput, setNewPriceInput] = useState('');
  const [newUnit, setNewUnit] = useState<'kg' | 'pack'>('kg');
  const [newIsPopular, setNewIsPopular] = useState(false);

  const filteredProducts = products.filter(
    (p) => p.name.includes(search) || p.code.includes(search)
  );

  const startEditing = (p: Product) => {
    setEditingId(p.id);
    const displayVal =
      settings.currencyDisplayUnit === 'TOMAN'
        ? rialToToman(p.pricePerKgRial)
        : p.pricePerKgRial;
    setEditPriceInput(String(displayVal));
  };

  const saveEdit = (product: Product) => {
    const val = parseFloat(editPriceInput);
    if (!isNaN(val) && val > 0) {
      const newPriceRial =
        settings.currencyDisplayUnit === 'TOMAN'
          ? tomanToRial(val)
          : Math.round(val);

      const updated = products.map((item) =>
        item.id === product.id ? { ...item, pricePerKgRial: newPriceRial } : item
      );
      onUpdateProducts(updated);
    }
    setEditingId(null);
  };

  const handleTogglePopular = (id: string) => {
    const updated = products.map((item) =>
      item.id === id ? { ...item, isPopular: !item.isPopular } : item
    );
    onUpdateProducts(updated);
  };

  const handleDeleteProduct = (id: string) => {
    if (confirm('آیا از حذف این کالا از نرخ‌نامه اطمینان دارید؟')) {
      const updated = products.filter((p) => p.id !== id);
      onUpdateProducts(updated);
    }
  };

  const handleResetDefaults = () => {
    if (confirm('آیا مایلید نرخ‌نامه به لیست پیش‌فرض اولیه بازگردانی شود؟')) {
      onUpdateProducts(DEFAULT_PRODUCTS);
    }
  };

  const handleCreateProduct = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !newPriceInput) return;

    const val = parseFloat(newPriceInput);
    if (isNaN(val) || val <= 0) return;

    const priceRial =
      settings.currencyDisplayUnit === 'TOMAN'
        ? tomanToRial(val)
        : Math.round(val);

    const newProd: Product = {
      id: `prod-custom-${Date.now()}`,
      code: newCode.trim() || String(Math.floor(700 + Math.random() * 200)),
      name: newName.trim(),
      category: newCategory,
      pricePerKgRial: priceRial,
      unit: newUnit,
      isPopular: newIsPopular,
    };

    onUpdateProducts([newProd, ...products]);
    setShowAddModal(false);
    // Reset form
    setNewName('');
    setNewCode('');
    setNewPriceInput('');
    setNewIsPopular(false);
  };

  const getCategoryLabel = (cat: ProductCategory) => {
    switch (cat) {
      case 'chicken':
        return 'مرغ و ماکیان';
      case 'beef':
        return 'گوساله';
      case 'lamb':
        return 'گوسفندی';
      case 'minced':
        return 'چرخ‌کرده';
      case 'marinated':
        return 'جوجه و طعم‌دار';
      default:
        return 'سایر';
    }
  };

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-2xl p-4 sm:p-5 shadow-xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-stone-800 pb-4 mb-4">
        <div>
          <h2 className="text-base sm:text-lg font-bold text-white flex items-center gap-2">
            <Package className="w-5 h-5 text-rose-500" />
            <span>مدیریت کالاها و نرخ‌نامه مصوب</span>
          </h2>
          <p className="text-xs text-stone-400 mt-0.5">
            کلیه مبالغ در دیتابیس بر حسب ریال ذخیره و مطابق واحد انتخابی (
            {settings.currencyDisplayUnit === 'TOMAN' ? 'تومان' : 'ریال'}) نمایش
            داده می‌شوند.
          </p>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1.5 bg-rose-700 hover:bg-rose-600 text-white text-xs font-bold px-3.5 py-2 rounded-xl transition cursor-pointer shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>افزودن کالای جدید</span>
          </button>

          <button
            onClick={handleResetDefaults}
            title="بازنشانی به اقلام اولیه"
            className="p-2 bg-stone-800 hover:bg-stone-700 text-stone-300 rounded-xl transition cursor-pointer"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Search Input */}
      <div className="relative mb-4 max-w-sm">
        <input
          type="text"
          placeholder="جستجوی کالا بر اساس نام یا کد..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-stone-950 border border-stone-800 rounded-xl px-4 py-2 pr-9 text-xs text-stone-100 placeholder-stone-500 focus:outline-none focus:border-rose-500"
        />
        <Search className="w-4 h-4 text-stone-500 absolute right-3 top-2.5" />
      </div>

      {/* Products Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-right text-xs">
          <thead>
            <tr className="border-b border-stone-800 text-stone-400">
              <th className="py-2.5 px-3">کد</th>
              <th className="py-2.5 px-3">نام قطعه / فرآورده گوشتی</th>
              <th className="py-2.5 px-3">دسته‌بندی</th>
              <th className="py-2.5 px-3 text-left">
                قیمت مصوب ({settings.currencyDisplayUnit === 'TOMAN' ? 'تومان' : 'ریال'} / کیلو)
              </th>
              <th className="py-2.5 px-3 text-center">پرفروش</th>
              <th className="py-2.5 px-3 text-center">عملیات</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-800/60">
            {filteredProducts.map((product) => {
              const isEditing = editingId === product.id;

              return (
                <tr key={product.id} className="hover:bg-stone-800/30 transition">
                  <td className="py-2.5 px-3 font-mono font-bold text-stone-400">
                    #{toPersianDigits(product.code)}
                  </td>
                  <td className="py-2.5 px-3 font-medium text-stone-100 text-sm">
                    {product.name}
                  </td>
                  <td className="py-2.5 px-3 text-stone-400">
                    <span className="bg-stone-800/80 px-2 py-0.5 rounded text-[11px] border border-stone-700/60">
                      {getCategoryLabel(product.category)}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-left">
                    {isEditing ? (
                      <div className="flex items-center gap-1.5 justify-end">
                        <input
                          type="number"
                          autoFocus
                          value={editPriceInput}
                          onChange={(e) => setEditPriceInput(e.target.value)}
                          className="w-28 bg-stone-950 border border-rose-500 rounded px-2 py-1 text-xs text-white text-left font-mono-digits"
                          dir="ltr"
                        />
                        <button
                          onClick={() => saveEdit(product)}
                          className="p-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded cursor-pointer"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="p-1 bg-stone-700 hover:bg-stone-600 text-stone-300 rounded cursor-pointer"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="font-bold text-amber-400 font-mono-digits text-sm">
                        {formatCurrency(
                          product.pricePerKgRial,
                          settings.currencyDisplayUnit
                        )}
                      </div>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <button
                      onClick={() => handleTogglePopular(product.id)}
                      className={`p-1 rounded transition cursor-pointer ${
                        product.isPopular
                          ? 'text-amber-400 bg-amber-950/60 border border-amber-800/60'
                          : 'text-stone-600 hover:text-stone-400'
                      }`}
                    >
                      <Sparkles className="w-4 h-4" />
                    </button>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <button
                        onClick={() => startEditing(product)}
                        title="ویرایش قیمت"
                        className="p-1.5 bg-stone-800 hover:bg-stone-700 text-stone-300 rounded-lg transition cursor-pointer"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDeleteProduct(product.id)}
                        title="حذف کالا"
                        className="p-1.5 bg-stone-800 hover:bg-rose-950 text-stone-400 hover:text-rose-400 rounded-lg transition cursor-pointer"
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
      </div>

      {/* Add Product Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5 max-w-md w-full shadow-2xl">
            <h3 className="font-bold text-white text-base mb-3 flex items-center gap-2">
              <Plus className="w-4 h-4 text-rose-500" />
              <span>افزودن محصول جدید به نرخ‌نامه</span>
            </h3>

            <form onSubmit={handleCreateProduct} className="space-y-3 text-xs">
              <div>
                <label className="block text-stone-300 mb-1">نام محصول:</label>
                <input
                  type="text"
                  required
                  placeholder="مثلاً: فیله شترمرغ تازه"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full bg-stone-950 border border-stone-700 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-rose-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-stone-300 mb-1">کد عددی کالا:</label>
                  <input
                    type="text"
                    placeholder="مثلاً ۵۰۵"
                    value={newCode}
                    onChange={(e) => setNewCode(e.target.value)}
                    className="w-full bg-stone-950 border border-stone-700 rounded-xl px-3 py-2 text-white font-mono-digits text-left"
                    dir="ltr"
                  />
                </div>

                <div>
                  <label className="block text-stone-300 mb-1">دسته‌بندی:</label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value as any)}
                    className="w-full bg-stone-950 border border-stone-700 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-rose-500"
                  >
                    <option value="beef">گوشت گوساله</option>
                    <option value="lamb">گوشت گوسفندی</option>
                    <option value="chicken">مرغ و ماکیان</option>
                    <option value="minced">چرخ‌کرده</option>
                    <option value="marinated">جوجه و طعم‌دار</option>
                    <option value="other">اقلام جانبی</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-stone-300 mb-1">
                    قیمت پایه (به {settings.currencyDisplayUnit === 'TOMAN' ? 'تومان' : 'ریال'}):
                  </label>
                  <input
                    type="number"
                    required
                    min="1"
                    placeholder={
                      settings.currencyDisplayUnit === 'TOMAN' ? '۳۵۰۰۰۰' : '۳۵۰۰۰۰۰'
                    }
                    value={newPriceInput}
                    onChange={(e) => setNewPriceInput(e.target.value)}
                    className="w-full bg-stone-950 border border-stone-700 rounded-xl px-3 py-2 text-white font-mono-digits text-left"
                    dir="ltr"
                  />
                </div>

                <div>
                  <label className="block text-stone-300 mb-1">واحد سنجش:</label>
                  <select
                    value={newUnit}
                    onChange={(e) => setNewUnit(e.target.value as 'kg' | 'pack')}
                    className="w-full bg-stone-950 border border-stone-700 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-rose-500"
                  >
                    <option value="kg">کیلوگرم (وزنی)</option>
                    <option value="pack">بسته‌ای / عددی</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="popCheck"
                  checked={newIsPopular}
                  onChange={(e) => setNewIsPopular(e.target.checked)}
                  className="w-4 h-4 rounded text-rose-600 bg-stone-950 border-stone-700"
                />
                <label htmlFor="popCheck" className="text-stone-300 cursor-pointer">
                  نمایش به عنوان کالای منتخب و پرفروش در صفحه اصلی
                </label>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-stone-800">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-stone-400 hover:text-white"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-rose-700 hover:bg-rose-600 text-white font-bold rounded-xl shadow-md"
                >
                  ذخیره کالا
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
