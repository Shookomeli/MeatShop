import React, { useState, useEffect, useCallback } from 'react';
import {
  Product,
  Invoice,
  InvoiceItem,
  ShopSettings,
  ScaleReading,
  CurrencyUnit,
} from './types';
import {
  loadProducts,
  saveProducts,
  loadInvoices,
  saveInvoice,
  deleteInvoice,
  loadSettings,
  saveSettings,
} from './services/storageService';
import { getScaleService, MockScale } from './services/scaleService';
import { Header } from './components/Header';
import { ScaleDisplay } from './components/ScaleDisplay';
import { ProductCatalog } from './components/ProductCatalog';
import { InvoiceBuilder } from './components/InvoiceBuilder';
import { InvoiceReceiptModal } from './components/InvoiceReceiptModal';
import { SalesHistory } from './components/SalesHistory';
import { ProductManager } from './components/ProductManager';
import { ScaleSettingsView } from './components/ScaleSettingsModal';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<'pos' | 'history' | 'products' | 'settings'>('pos');
  const [products, setProducts] = useState<Product[]>(loadProducts);
  const [invoices, setInvoices] = useState<Invoice[]>(loadInvoices);
  const [settings, setSettings] = useState<ShopSettings>(loadSettings);
  const [draftItems, setDraftItems] = useState<InvoiceItem[]>([]);
  const [activeReceiptInvoice, setActiveReceiptInvoice] = useState<Invoice | null>(null);

  const [scaleReading, setScaleReading] = useState<ScaleReading>({
    grossWeight: 0,
    tareWeight: 0,
    netWeight: 0,
    isStable: true,
    isZero: true,
    isConnected: true,
    errorMessage: null,
    unit: 'kg',
    timestamp: Date.now(),
  });

  // Initialize and subscribe to scale hardware/mock service
  useEffect(() => {
    const scale = getScaleService(settings.scaleMode);
    const unsubscribe = scale.subscribe((reading) => {
      setScaleReading(reading);
    });

    return () => {
      unsubscribe();
    };
  }, [settings.scaleMode]);

  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);

  const showNotice = useCallback((msg: string) => {
    setNoticeMessage(msg);
    setTimeout(() => {
      setNoticeMessage(null);
    }, 3500);
  }, []);

  // Scale Hardware Actions
  const handleZero = useCallback(() => {
    try {
      const scale = getScaleService(settings.scaleMode);
      scale.zero();
    } catch (e: any) {
      showNotice(e.message || 'خطا در صفر کردن کفه');
    }
  }, [settings.scaleMode, showNotice]);

  const handleTare = useCallback(() => {
    try {
      const scale = getScaleService(settings.scaleMode);
      scale.tare();
    } catch (e: any) {
      showNotice(e.message || 'خطا در پارسنگ کفه');
    }
  }, [settings.scaleMode, showNotice]);

  const handleClearTare = useCallback(() => {
    try {
      const scale = getScaleService(settings.scaleMode);
      scale.clear_tare();
    } catch (e: any) {
      console.error(e);
    }
  }, [settings.scaleMode]);

  const handleSetWeight = useCallback(
    (weightKg: number) => {
      const scale = getScaleService(settings.scaleMode);
      scale.setTargetWeight(weightKg);
    },
    [settings.scaleMode]
  );

  const handleReconnectScale = useCallback(async () => {
    const scale = getScaleService(settings.scaleMode);
    await scale.connect();
  }, [settings.scaleMode]);

  const handleSimulateError = useCallback(
    (type: 'disconnect' | 'unstable' | 'clear') => {
      const scale = getScaleService(settings.scaleMode) as MockScale;
      if (!scale) return;

      if (type === 'disconnect') {
        scale.disconnect();
      } else if (type === 'unstable') {
        scale.setErrorMessage('بار روی کفه در حال نوسان است (UnstableWeightError)');
        scale.toggleJitter(true);
        scale.setTargetWeight(scaleReading.grossWeight + 0.05);
      } else {
        scale.connect();
        scale.setErrorMessage(null);
        scale.toggleJitter(true);
      }
    },
    [settings.scaleMode, scaleReading.grossWeight]
  );

  // Add Item to Invoice Cart
  const handleAddItemToInvoice = useCallback(
    (product: Product, weightKg: number) => {
      // Calculate total in whole-number Rial
      const roundedWeight = Math.round(weightKg * 1000) / 1000;
      const totalRial = Math.round(product.pricePerKgRial * roundedWeight);

      const newItem: InvoiceItem = {
        id: `item-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
        productId: product.id,
        productName: product.name,
        category: product.category,
        unit: product.unit,
        unitPriceRial: product.pricePerKgRial,
        weightKg: roundedWeight,
        tareKg: scaleReading.tareWeight,
        grossWeightKg: scaleReading.grossWeight,
        totalRial,
        timestamp: Date.now(),
      };

      setDraftItems((prev) => [...prev, newItem]);

      // If shop has auto-tare enabled, tare after adding
      if (settings.autoTareOnAdd) {
        handleTare();
      }
    },
    [scaleReading, settings.autoTareOnAdd, handleTare]
  );

  const handleRemoveDraftItem = useCallback((id: string) => {
    setDraftItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const handleClearDraft = useCallback(() => {
    if (draftItems.length === 0) return;
    setDraftItems([]);
    showNotice('پیش‌نویس فاکتور پاک شد');
  }, [draftItems.length, showNotice]);

  const handleFinalizeInvoice = useCallback((invoice: Invoice) => {
    saveInvoice(invoice);
    setInvoices((prev) => [invoice, ...prev]);
    setDraftItems([]);
    setActiveReceiptInvoice(invoice);
  }, []);

  const handleDeleteInvoice = useCallback((id: string) => {
    deleteInvoice(id);
    setInvoices((prev) => prev.filter((inv) => inv.id !== id));
  }, []);

  const handleToggleCurrency = useCallback(() => {
    const nextUnit: CurrencyUnit = settings.currencyDisplayUnit === 'TOMAN' ? 'RIAL' : 'TOMAN';
    const updated: ShopSettings = { ...settings, currencyDisplayUnit: nextUnit };
    setSettings(updated);
    saveSettings(updated);
  }, [settings]);

  const handleSaveSettings = useCallback((newSettings: ShopSettings) => {
    setSettings(newSettings);
    saveSettings(newSettings);
  }, []);

  const handleUpdateProducts = useCallback((newProducts: Product[]) => {
    setProducts(newProducts);
    saveProducts(newProducts);
  }, []);

  return (
    <div className="min-h-screen bg-stone-900 text-stone-100 flex flex-col">
      {/* Global Header */}
      <Header
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        scaleReading={scaleReading}
        settings={settings}
        onToggleCurrency={handleToggleCurrency}
        onReconnectScale={handleReconnectScale}
        invoicesCount={invoices.length}
      />

      {/* Main Content Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-3 sm:p-5 lg:p-6">
        {noticeMessage && (
          <div className="mb-3 p-3 bg-amber-950/80 border border-amber-500/50 text-amber-200 rounded-lg text-sm font-medium flex items-center justify-between shadow-lg">
            <span>⚠️ {noticeMessage}</span>
            <button
              onClick={() => setNoticeMessage(null)}
              className="text-amber-400 hover:text-white text-xs px-2 py-0.5 rounded bg-amber-900/50 hover:bg-amber-800"
            >
              بستن
            </button>
          </div>
        )}

        {currentTab === 'pos' && (
          <div className="space-y-4">
            {/* Top Industrial Scale Indicator */}
            <ScaleDisplay
              scaleReading={scaleReading}
              settings={settings}
              onZero={handleZero}
              onTare={handleTare}
              onClearTare={handleClearTare}
              onSetWeight={handleSetWeight}
            />

            {/* Split Grid: Product Catalog & Draft Invoice Builder */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
              {/* Right Col: Product Catalog (7 columns on desktop) */}
              <div className="lg:col-span-7">
                <ProductCatalog
                  products={products}
                  scaleReading={scaleReading}
                  settings={settings}
                  onAddItemToInvoice={handleAddItemToInvoice}
                />
              </div>

              {/* Left Col: Invoice Builder (5 columns on desktop) */}
              <div className="lg:col-span-5">
                <InvoiceBuilder
                  items={draftItems}
                  settings={settings}
                  onRemoveItem={handleRemoveDraftItem}
                  onClearInvoice={handleClearDraft}
                  onFinalizeInvoice={handleFinalizeInvoice}
                  onTareScale={handleTare}
                  onClearScaleWeight={() => handleSetWeight(0)}
                />
              </div>
            </div>
          </div>
        )}

        {currentTab === 'history' && (
          <SalesHistory
            invoices={invoices}
            settings={settings}
            onViewInvoice={(inv) => setActiveReceiptInvoice(inv)}
            onDeleteInvoice={handleDeleteInvoice}
          />
        )}

        {currentTab === 'products' && (
          <ProductManager
            products={products}
            settings={settings}
            onUpdateProducts={handleUpdateProducts}
          />
        )}

        {currentTab === 'settings' && (
          <ScaleSettingsView
            settings={settings}
            onSaveSettings={handleSaveSettings}
            onSimulateError={handleSimulateError}
          />
        )}
      </main>

      {/* Printable Receipt Modal */}
      <InvoiceReceiptModal
        invoice={activeReceiptInvoice}
        settings={settings}
        onClose={() => setActiveReceiptInvoice(null)}
      />
    </div>
  );
};

export default App;
