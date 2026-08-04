import { describe, expect, it } from "vitest";
import {
  DEVELOPMENT_BIVARIATE_COLORS,
  DEVELOPMENT_UNIVARIATE_COLORS,
  classRange,
  contrastRatio,
  legendModel,
  legendTextColor,
} from "./legend";
import { createVariableRegistry, variableById } from "./registry";
import { artificialCompatibleVariable } from "./test-fixtures";

describe("manifest-driven legends", () => {
  it("renders all nine bivariate states as paired text with exact threshold ownership", () => {
    const spei = variableById("spei_3");
    const utci = variableById("utci_daymax_median");
    const model = legendModel(spei, utci);

    expect(model.cells).toHaveLength(9);
    expect(new Set(model.cells.map(({ label }) => label))).toHaveLength(9);
    expect(model.cells.every(({ label }) => label.includes(" × "))).toBe(true);
    expect(classRange(spei, 0)).toBe("≤ -1.5 standard deviations");
    expect(classRange(spei, 1)).toBe("> -1.5 and ≤ -1 standard deviations");
    expect(classRange(utci, 0)).toBe("< 9 °C");
    expect(classRange(utci, 1)).toBe("≥ 9 and ≤ 26 °C");
  });

  it("supports an artificial third variable without changing registry or legend code", () => {
    const spei = variableById("spei_3");
    const utci = variableById("utci_daymax_median");
    const artificial = artificialCompatibleVariable(utci);
    const registry = createVariableRegistry([spei, utci, artificial]);
    const model = legendModel(spei, registry.byId.get(artificial.id)!);

    expect(registry.variables).toHaveLength(3);
    expect(model.cells).toHaveLength(9);
    expect(model.yLabel).toContain("not climate observations");
  });

  it("keeps orientation ordered by the selected X and Y manifests after a swap", () => {
    const spei = variableById("spei_3");
    const utci = variableById("utci_daymax_median");
    const original = legendModel(spei, utci);
    const swapped = legendModel(utci, spei);

    expect(original.xLabel).toBe(spei.label);
    expect(original.yLabel).toBe(utci.label);
    expect(swapped.xLabel).toBe(utci.label);
    expect(swapped.yLabel).toBe(spei.label);
    expect(swapped.cells[0].label).not.toBe(original.cells[0].label);
  });

  it("keeps legend text at WCAG AA contrast across every development color", () => {
    for (const color of [
      ...DEVELOPMENT_BIVARIATE_COLORS,
      ...DEVELOPMENT_UNIVARIATE_COLORS,
    ]) {
      expect(contrastRatio(legendTextColor(color), color)).toBeGreaterThanOrEqual(4.5);
    }
  });
});
