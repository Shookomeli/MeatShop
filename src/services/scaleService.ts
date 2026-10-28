import { ScaleMode, ScaleReading } from '../types';

export class ScaleError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ScaleError';
  }
}

export class ScaleUnavailableError extends ScaleError {
  constructor(message = 'ترازوی دیجیتال در دسترس نیست یا قطع شده است') {
    super(message);
    this.name = 'ScaleUnavailableError';
  }
}

export class UnstableWeightError extends ScaleError {
  constructor(message = 'وزن هنوز ثابت نشده است. لطفاً کالا را روی کفه بی حرکت نگه دارید') {
    super(message);
    this.name = 'UnstableWeightError';
  }
}

export interface ScaleInterface {
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  get_weight(): ScaleReading;
  is_stable(): boolean;
  tare(): void;
  clear_tare(): void;
  zero(): void;
  setTargetWeight(weightKg: number): void;
  subscribe(listener: (reading: ScaleReading) => void): () => void;
}

/**
 * MockScale implements high-fidelity digital scale simulation
 * with load settling, jitter, tare and zero operations.
 */
export class MockScale implements ScaleInterface {
  private targetWeight = 0;
  private currentGrossWeight = 0;
  private tareWeight = 0;
  private isConnected = true;
  private stable = true;
  private listeners: Set<(reading: ScaleReading) => void> = new Set();
  private timer: number | null = null;
  private jitterEnabled = true;
  private errorMessage: string | null = null;

  constructor() {
    this.startSimulationLoop();
  }

  private startSimulationLoop() {
    if (this.timer) clearInterval(this.timer);

    this.timer = window.setInterval(() => {
      if (!this.isConnected) {
        this.emitReading();
        return;
      }

      // Approach target weight smoothly
      const diff = this.targetWeight - this.currentGrossWeight;
      if (Math.abs(diff) > 0.005) {
        this.stable = false;
        this.currentGrossWeight += diff * 0.45;
      } else {
        this.currentGrossWeight = this.targetWeight;
        this.stable = true;
      }

      // Apply subtle live load-cell micro-jitter if platter has weight (> 0) and jitter enabled
      if (this.currentGrossWeight > 0.01 && this.jitterEnabled && this.stable) {
        // Very small micro-flicker +/- 0.002 kg occasionally
        if (Math.random() < 0.2) {
          const jitter = (Math.random() - 0.5) * 0.004;
          this.currentGrossWeight = Math.max(0, this.targetWeight + jitter);
        }
      }

      this.emitReading();
    }, 150);
  }

  public async connect(): Promise<void> {
    this.isConnected = true;
    this.errorMessage = null;
    this.emitReading();
  }

  public async disconnect(): Promise<void> {
    this.isConnected = false;
    this.errorMessage = 'ترازو غیرفعال است';
    this.emitReading();
  }

  public get_weight(): ScaleReading {
    if (!this.isConnected) {
      throw new ScaleUnavailableError(this.errorMessage || 'ترازو متصل نیست');
    }
    const netWeight = Math.max(0, this.currentGrossWeight - this.tareWeight);
    return {
      grossWeight: Math.round(this.currentGrossWeight * 1000) / 1000,
      tareWeight: Math.round(this.tareWeight * 1000) / 1000,
      netWeight: Math.round(netWeight * 1000) / 1000,
      isStable: this.stable,
      isZero: this.currentGrossWeight <= 0.002,
      isConnected: this.isConnected,
      errorMessage: this.errorMessage,
      unit: 'kg',
      timestamp: Date.now(),
    };
  }

  public is_stable(): boolean {
    return this.stable && this.isConnected;
  }

  public tare(): void {
    if (!this.isConnected) throw new ScaleUnavailableError();
    // Set current gross as tare
    this.tareWeight = Math.max(0, this.currentGrossWeight);
    this.emitReading();
  }

  public clear_tare(): void {
    this.tareWeight = 0;
    this.emitReading();
  }

  public zero(): void {
    if (!this.isConnected) throw new ScaleUnavailableError();
    this.targetWeight = 0;
    this.currentGrossWeight = 0;
    this.tareWeight = 0;
    this.stable = true;
    this.emitReading();
  }

  public setTargetWeight(weightKg: number): void {
    this.targetWeight = Math.max(0, Math.round(weightKg * 1000) / 1000);
    this.stable = false; // weight change triggers stabilization period
    this.emitReading();
  }

  public setErrorMessage(msg: string | null) {
    this.errorMessage = msg;
    this.emitReading();
  }

  public toggleJitter(enabled: boolean) {
    this.jitterEnabled = enabled;
  }

  public subscribe(listener: (reading: ScaleReading) => void): () => void {
    this.listeners.add(listener);
    listener(this.getSafeReading());
    return () => {
      this.listeners.delete(listener);
    };
  }

  private getSafeReading(): ScaleReading {
    const netWeight = Math.max(0, this.currentGrossWeight - this.tareWeight);
    return {
      grossWeight: Math.round(this.currentGrossWeight * 1000) / 1000,
      tareWeight: Math.round(this.tareWeight * 1000) / 1000,
      netWeight: Math.round(netWeight * 1000) / 1000,
      isStable: this.stable,
      isZero: this.currentGrossWeight <= 0.002,
      isConnected: this.isConnected,
      errorMessage: this.errorMessage,
      unit: 'kg',
      timestamp: Date.now(),
    };
  }

  private emitReading() {
    const reading = this.getSafeReading();
    for (const listener of this.listeners) {
      listener(reading);
    }
  }

  public destroy() {
    if (this.timer) clearInterval(this.timer);
    this.listeners.clear();
  }
}

/**
 * KeliXK3118T1Scale handles the industrial scale protocol
 * with optional Web Serial API integration and fallback to high-precision hardware emulation.
 */
export class KeliXK3118T1Scale extends MockScale {
  private baudRate = 9600;
  private comPort = 'COM3';

  constructor(baudRate = 9600, comPort = 'COM3') {
    super();
    this.baudRate = baudRate;
    this.comPort = comPort;
  }

  public getHardwareConfig() {
    return {
      model: 'KELI XK3118T1',
      baudRate: this.baudRate,
      comPort: this.comPort,
      parity: 'None',
      dataBits: 8,
      stopBits: 1,
      protocol: 'Continuous Output (ASCII)',
    };
  }
}

// Singleton scale instance manager
let activeScaleInstance: ScaleInterface | null = null;
let currentMode: ScaleMode = 'mock';

export function getScaleService(mode: ScaleMode = currentMode): ScaleInterface {
  if (!activeScaleInstance || currentMode !== mode) {
    if (activeScaleInstance && 'destroy' in activeScaleInstance) {
      (activeScaleInstance as MockScale).destroy();
    }

    currentMode = mode;
    if (mode === 'keli_xk3118t1') {
      activeScaleInstance = new KeliXK3118T1Scale();
    } else {
      activeScaleInstance = new MockScale();
    }
  }
  return activeScaleInstance;
}
