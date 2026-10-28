import { CurrencyUnit } from '../types';

/**
 * Converts Latin digits (0-9) to Eastern Arabic / Persian digits (۰-۹)
 */
export function toPersianDigits(input: number | string): string {
  const persianDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
  return String(input).replace(/[0-9]/g, (w) => persianDigits[+w]);
}

/**
 * 1 Toman = 10 Rial
 */
export function rialToToman(rialAmount: number): number {
  return Math.floor(rialAmount / 10);
}

export function tomanToRial(tomanAmount: number): number {
  return Math.round(tomanAmount * 10);
}

/**
 * Format a Rial amount according to the chosen display unit (TOMAN or RIAL).
 * Always calculates from whole-number Rial stored in state.
 */
export function formatCurrency(
  rialAmount: number,
  displayUnit: CurrencyUnit,
  options: {
    usePersianDigits?: boolean;
    withUnitLabel?: boolean;
  } = {}
): string {
  const { usePersianDigits = true, withUnitLabel = true } = options;

  let displayValue: number;
  let unitLabel: string;

  if (displayUnit === 'TOMAN') {
    displayValue = rialToToman(rialAmount);
    unitLabel = 'تومان';
  } else {
    displayValue = rialAmount;
    unitLabel = 'ریال';
  }

  // Format with thousand separators
  const formattedNumber = new Intl.NumberFormat('en-US').format(Math.round(displayValue));
  const resultString = usePersianDigits ? toPersianDigits(formattedNumber) : formattedNumber;

  if (withUnitLabel) {
    return `${resultString} ${unitLabel}`;
  }
  return resultString;
}

/**
 * Formats weight in kg with 3 decimal places (e.g. 1.250 kg)
 */
export function formatWeight(
  weightKg: number,
  options: {
    usePersianDigits?: boolean;
    withUnit?: boolean;
  } = {}
): string {
  const { usePersianDigits = true, withUnit = true } = options;
  const formatted = weightKg.toFixed(3);
  const result = usePersianDigits ? toPersianDigits(formatted) : formatted;
  return withUnit ? `${result} کیلوگرم` : result;
}
