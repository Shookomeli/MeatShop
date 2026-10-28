import { Product, Invoice, ShopSettings } from '../types';

const STORAGE_KEYS = {
  PRODUCTS: 'meat_shop_products_v1',
  INVOICES: 'meat_shop_invoices_v1',
  SETTINGS: 'meat_shop_settings_v1',
};

// Initial default Iranian meat cuts & poultry catalog
// Prices stored in whole-number RIAL (e.g., 3,500,000 Rial = 350,000 Toman)
export const DEFAULT_PRODUCTS: Product[] = [
  // Chicken / ماکیان
  {
    id: 'prod-chk-01',
    code: '101',
    name: 'سینه مرغ بدون پوست و استخوان',
    category: 'chicken',
    pricePerKgRial: 2450000, // 245,000 Toman
    unit: 'kg',
    isPopular: true,
  },
  {
    id: 'prod-chk-02',
    code: '102',
    name: 'ران مرغ با پوست (کشتار روز)',
    category: 'chicken',
    pricePerKgRial: 1850000, // 185,000 Toman
    unit: 'kg',
    isPopular: true,
  },
  {
    id: 'prod-chk-03',
    code: '103',
    name: 'فیله مرغ ممتاز پاک‌شده',
    category: 'chicken',
    pricePerKgRial: 2950000, // 295,000 Toman
    unit: 'kg',
    isPopular: true,
  },
  {
    id: 'prod-chk-04',
    code: '104',
    name: 'بال و بازوی مرغ زعفرانی',
    category: 'marinated',
    pricePerKgRial: 2100000, // 210,000 Toman
    unit: 'kg',
  },
  {
    id: 'prod-chk-05',
    code: '105',
    name: 'مرغ کامل پاک‌شده (بسته‌بندی)',
    category: 'chicken',
    pricePerKgRial: 1450000, // 145,000 Toman
    unit: 'kg',
  },

  // Beef / گوشت گوساله
  {
    id: 'prod-bef-01',
    code: '201',
    name: 'راسته گوساله نر ممتاز',
    category: 'beef',
    pricePerKgRial: 6800000, // 680,000 Toman
    unit: 'kg',
    isPopular: true,
  },
  {
    id: 'prod-bef-02',
    code: '202',
    name: 'فیله گوساله بدون چربی',
    category: 'beef',
    pricePerKgRial: 7900000, // 790,000 Toman
    unit: 'kg',
    isPopular: true,
  },
  {
    id: 'prod-bef-03',
    code: '203',
    name: 'ران گوساله بی‌استخوان',
    category: 'beef',
    pricePerKgRial: 6300000, // 630,000 Toman
    unit: 'kg',
  },
  {
    id: 'prod-bef-04',
    code: '204',
    name: 'قلوه‌گاه گوساله (جهت چرخ‌کرده)',
    category: 'beef',
    pricePerKgRial: 4800000, // 480,000 Toman
    unit: 'kg',
  },

  // Lamb / گوشت گوسفندی
  {
    id: 'prod-lmb-01',
    code: '301',
    name: 'شقه گوسفندی با استخوان (نرینه)',
    category: 'lamb',
    pricePerKgRial: 7400000, // 740,000 Toman
    unit: 'kg',
    isPopular: true,
  },
  {
    id: 'prod-lmb-02',
    code: '302',
    name: 'ران گوسفندی با قلم',
    category: 'lamb',
    pricePerKgRial: 8200000, // 820,000 Toman
    unit: 'kg',
    isPopular: true,
  },
  {
    id: 'prod-lmb-03',
    code: '303',
    name: 'سردست گوسفندی با دنده',
    category: 'lamb',
    pricePerKgRial: 7600000, // 760,000 Toman
    unit: 'kg',
  },
  {
    id: 'prod-lmb-04',
    code: '304',
    name: 'ماهیچه گوسفندی تازه',
    category: 'lamb',
    pricePerKgRial: 8900000, // 890,000 Toman
    unit: 'kg',
  },
  {
    id: 'prod-lmb-05',
    code: '305',
    name: 'گردن گوسفندی لذیذ',
    category: 'lamb',
    pricePerKgRial: 7100000, // 710,000 Toman
    unit: 'kg',
  },

  // Minced / چرخ‌کرده
  {
    id: 'prod-mnc-01',
    code: '401',
    name: 'گوشت چرخ‌کرده مخلوط (گوساله و گوسفندی)',
    category: 'minced',
    pricePerKgRial: 5900000, // 590,000 Toman
    unit: 'kg',
    isPopular: true,
  },
  {
    id: 'prod-mnc-02',
    code: '402',
    name: 'چرخ‌کرده مرغ و بوقلمون',
    category: 'minced',
    pricePerKgRial: 2600000, // 260,000 Toman
    unit: 'kg',
  },

  // Marinated / محصولات مرینیت‌شده و فرآوری‌شده
  {
    id: 'prod-mar-01',
    code: '501',
    name: 'جوجه کباب با استخوان زعفرانی',
    category: 'marinated',
    pricePerKgRial: 2350000, // 235,000 Toman
    unit: 'kg',
    isPopular: true,
  },
  {
    id: 'prod-mar-02',
    code: '502',
    name: 'جوجه کباب بی‌استخوان ماستی و ترش',
    category: 'marinated',
    pricePerKgRial: 2750000, // 275,000 Toman
    unit: 'kg',
  },
  {
    id: 'prod-mar-03',
    code: '503',
    name: 'شنیسل مرغ سوخاری آماده پخت',
    category: 'marinated',
    pricePerKgRial: 2800000, // 280,000 Toman
    unit: 'kg',
  },
  {
    id: 'prod-mar-04',
    code: '504',
    name: 'کباب برگ گوساله آماده سیخ',
    category: 'marinated',
    pricePerKgRial: 8500000, // 850,000 Toman
    unit: 'kg',
  },

  // Other / اقلام جانبی
  {
    id: 'prod-oth-01',
    code: '601',
    name: 'دنبه تازه گوسفندی',
    category: 'other',
    pricePerKgRial: 3900000, // 390,000 Toman
    unit: 'kg',
  },
  {
    id: 'prod-oth-02',
    code: '602',
    name: 'قلم گوساله خردشده (جهت سوپ)',
    category: 'other',
    pricePerKgRial: 900000, // 90,000 Toman
    unit: 'kg',
  },
];

export const DEFAULT_SETTINGS: ShopSettings = {
  shopName: 'واکا پروتئین (Vaka Protein)',
  tagline: 'توزیع مستقیم گوشت گرم و مرغ کشتار روز',
  phone: '۰۲۱-۸۸۴۵۶۷۸۹',
  address: 'تهران، خیابان شریعتی، نبش خیابان میثاق، پلاک ۱۲۴',
  currencyDisplayUnit: 'TOMAN', // Default unit as indicated in README
  scaleMode: 'mock',
  taxPercent: 0,
  receiptFooter: 'از حسن انتخاب و خرید شما صمیمانه سپاسگزاریم • جنس فروخته‌شده پس از خروج تعویض نمی‌گردد',
  autoTareOnAdd: false,
  baudRate: 9600,
  comPort: 'COM3',
};

// Storage helper functions
export function loadProducts(): Product[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.PRODUCTS);
    if (!raw) {
      saveProducts(DEFAULT_PRODUCTS);
      return DEFAULT_PRODUCTS;
    }
    return JSON.parse(raw);
  } catch {
    return DEFAULT_PRODUCTS;
  }
}

export function saveProducts(products: Product[]): void {
  try {
    localStorage.setItem(STORAGE_KEYS.PRODUCTS, JSON.stringify(products));
  } catch (err) {
    console.error('Failed to save products to localStorage', err);
  }
}

export function loadInvoices(): Invoice[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.INVOICES);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveInvoice(invoice: Invoice): void {
  try {
    const current = loadInvoices();
    const updated = [invoice, ...current];
    localStorage.setItem(STORAGE_KEYS.INVOICES, JSON.stringify(updated));
  } catch (err) {
    console.error('Failed to save invoice', err);
  }
}

export function deleteInvoice(id: string): void {
  try {
    const current = loadInvoices();
    const filtered = current.filter(inv => inv.id !== id);
    localStorage.setItem(STORAGE_KEYS.INVOICES, JSON.stringify(filtered));
  } catch (err) {
    console.error('Failed to delete invoice', err);
  }
}

export function loadSettings(): ShopSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.SETTINGS);
    if (!raw) {
      saveSettings(DEFAULT_SETTINGS);
      return DEFAULT_SETTINGS;
    }
    const parsed = JSON.parse(raw);
    const settings = { ...DEFAULT_SETTINGS, ...parsed };
    if (!settings.shopName || settings.shopName.includes('البرز')) {
      settings.shopName = 'واکا پروتئین (Vaka Protein)';
    }
    return settings;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveSettings(settings: ShopSettings): void {
  try {
    localStorage.setItem(STORAGE_KEYS.SETTINGS, JSON.stringify(settings));
  } catch (err) {
    console.error('Failed to save settings', err);
  }
}
