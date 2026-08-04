export const MONTHS = [
  { number: 1, short: "Jan", full: "January" },
  { number: 2, short: "Feb", full: "February" },
  { number: 3, short: "Mar", full: "March" },
  { number: 4, short: "Apr", full: "April" },
  { number: 5, short: "May", full: "May" },
  { number: 6, short: "Jun", full: "June" },
  { number: 7, short: "Jul", full: "July" },
  { number: 8, short: "Aug", full: "August" },
  { number: 9, short: "Sep", full: "September" },
  { number: 10, short: "Oct", full: "October" },
  { number: 11, short: "Nov", full: "November" },
  { number: 12, short: "Dec", full: "December" },
] as const;

export const ALL_MONTHS_MASK = 0xfff;

export function validateMask(mask: number): number {
  if (!Number.isInteger(mask) || mask < 1 || mask > ALL_MONTHS_MASK) {
    throw new Error("Month mask must be an integer between 1 and 4095.");
  }
  return mask;
}

export function monthsToMask(months: readonly number[]): number {
  let mask = 0;
  for (const month of months) {
    if (!Number.isInteger(month) || month < 1 || month > 12) {
      throw new Error("Months must be integers from 1 through 12.");
    }
    mask |= 1 << (month - 1);
  }
  return validateMask(mask);
}

export function maskToMonths(mask: number): number[] {
  validateMask(mask);
  return MONTHS.filter(({ number }) => (mask & (1 << (number - 1))) !== 0).map(
    ({ number }) => number,
  );
}

export function maskToHex(mask: number): string {
  return validateMask(mask).toString(16).padStart(3, "0");
}

export function hexToMask(value: string): number {
  if (!/^[0-9a-f]{3}$/.test(value)) {
    throw new Error("Month mask must use three lowercase hexadecimal digits.");
  }
  return validateMask(Number.parseInt(value, 16));
}

export function formatPeriod(mask: number): string {
  const selected = maskToMonths(mask);
  if (mask === ALL_MONTHS_MASK) {
    return "All year";
  }

  const runs: number[][] = [];
  for (const month of selected) {
    const current = runs.at(-1);
    if (!current || month !== current.at(-1)! + 1) {
      runs.push([month]);
    } else {
      current.push(month);
    }
  }
  return runs
    .map((run) => {
      const first = MONTHS[run[0] - 1].short;
      const last = MONTHS[run.at(-1)! - 1].short;
      return run.length === 1 ? first : `${first}–${last}`;
    })
    .join(", ");
}

export interface ToggleResult {
  mask: number;
  changed: boolean;
  announcement: string | null;
}

export function toggleMonth(mask: number, month: number): ToggleResult {
  validateMask(mask);
  if (!Number.isInteger(month) || month < 1 || month > 12) {
    throw new Error("Month must be an integer from 1 through 12.");
  }
  const bit = 1 << (month - 1);
  const isSelected = (mask & bit) !== 0;
  if (isSelected && mask === bit) {
    return {
      mask,
      changed: false,
      announcement: "Keep at least one month selected.",
    };
  }
  return {
    mask: mask ^ bit,
    changed: true,
    announcement: null,
  };
}
