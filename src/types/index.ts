export type CurrencyUnit = 'TOMAN' | 'RIAL';

export type ScaleMode = 'mock' | 'keli_xk3118t1';

export type ProductCategory = 'chicken' | 'beef' | 'lamb' | 'minced' | 'marinated' | 'other';

export interface ScaleReading {
  grossWeight: number; // in kg
  tareWeight: number;  // in kg
  netWeight: number;   // in kg (gross - tare)
  isStable: boolean;
  isZero: boolean;
  isConnected: boolean;
  errorMessage: string | null;
  unit: 'kg';
  timestamp: number;
}

export interface Product {
  id: string;
  code: string;
  name: string;
  category: ProductCategory;
  pricePerKgRial: number; // Stored in whole-number RIAL as required by DB schema rules
  unit: 'kg' | 'pack';
  isPopular?: boolean;
  iconName?: string;
}

export interface InvoiceItem {
  id: string;
  productId: string;
  productName: string;
  category: ProductCategory;
  unit: 'kg' | 'pack';
  unitPriceRial: number;
  weightKg: number;
  tareKg: number;
  grossWeightKg: number;
  totalRial: number;
  timestamp: number;
}

export interface Invoice {
  id: string;
  invoiceNumber: string;
  createdAt: string; // ISO format
  items: InvoiceItem[];
  totalWeightKg: number;
  subtotalRial: number;
  discountRial: number;
  taxRial: number;
  finalAmountRial: number;
  customerName?: string;
  customerPhone?: string;
  paymentMethod: 'cash' | 'card' | 'credit';
  notes?: string;
}

export interface ShopSettings {
  shopName: string;
  tagline: string;
  phone: string;
  address: string;
  currencyDisplayUnit: CurrencyUnit;
  scaleMode: ScaleMode;
  taxPercent: number;
  receiptFooter: string;
  autoTareOnAdd: boolean;
  baudRate: number;
  comPort: string;
}
