import { describe, expect, it } from "vitest";
import {
  ALL_MONTHS_MASK,
  formatPeriod,
  hexToMask,
  maskToHex,
  maskToMonths,
  monthsToMask,
  toggleMonth,
} from "./months";

describe("month masks", () => {
  it("round-trips every non-empty month selection", () => {
    for (let mask = 1; mask <= ALL_MONTHS_MASK; mask += 1) {
      expect(monthsToMask(maskToMonths(mask))).toBe(mask);
      expect(hexToMask(maskToHex(mask))).toBe(mask);
    }
  });

  it("supports arbitrary disjoint months", () => {
    const mask = monthsToMask([1, 4, 9]);

    expect(maskToHex(mask)).toBe("109");
    expect(maskToMonths(mask)).toEqual([1, 4, 9]);
    expect(formatPeriod(mask)).toBe("Jan, Apr, Sep");
  });

  it("protects the final selected month", () => {
    const januaryOnly = monthsToMask([1]);

    expect(toggleMonth(januaryOnly, 1)).toEqual({
      mask: januaryOnly,
      changed: false,
      announcement: "Keep at least one month selected.",
    });
    expect(toggleMonth(januaryOnly, 4).mask).toBe(monthsToMask([1, 4]));
  });
});
