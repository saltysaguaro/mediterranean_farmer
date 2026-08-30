import { describe, expect, it } from "vitest";
import {
  SICILY_BIVARIATE_COLORS_V1,
  SICILY_UNIVARIATE_COLORS_V1,
  classRange,
  contrastRatio,
  legendModel,
  legendTextColor,
} from "./legend";
import { createVariableRegistry, variableById } from "./registry";
import { artificialCompatibleVariable } from "./test-fixtures";

type Rgb = readonly [number, number, number];
type ColorMatrix = readonly [Rgb, Rgb, Rgb];

const COLOR_VISION_MATRICES: Record<string, ColorMatrix> = {
  protanopia: [
    [0.152286, 1.052583, -0.204868],
    [0.114503, 0.786281, 0.099216],
    [-0.003882, -0.048116, 1.051998],
  ],
  deuteranopia: [
    [0.367322, 0.860646, -0.227968],
    [0.280085, 0.672501, 0.047413],
    [-0.01182, 0.04294, 0.968881],
  ],
  tritanopia: [
    [1.255528, -0.076749, -0.178779],
    [-0.078411, 0.930809, 0.147602],
    [0.004733, 0.691367, 0.3039],
  ],
};

function rgb(color: string): Rgb {
  const channels = color
    .replace("#", "")
    .match(/.{2}/g)!
    .map((channel) => Number.parseInt(channel, 16) / 255);
  return [channels[0], channels[1], channels[2]];
}

function simulate(color: string, matrix: ColorMatrix): Rgb {
  const source = rgb(color);
  return matrix.map((row) =>
    Math.max(0, Math.min(1, row.reduce((sum, value, index) => sum + value * source[index], 0))),
  ) as unknown as Rgb;
}

function distance(left: Rgb, right: Rgb): number {
  return Math.hypot(...left.map((value, index) => value - right[index])) * 255;
}

function minimumPairDistance(colors: readonly Rgb[]): number {
  const distances: number[] = [];
  for (const [index, left] of colors.entries()) {
    for (const right of colors.slice(index + 1)) {
      distances.push(distance(left, right));
    }
  }
  return Math.min(...distances);
}

function displayLuminance(color: string): number {
  const [red, green, blue] = rgb(color);
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

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

  it("keeps legend text at WCAG AA contrast across every production color", () => {
    for (const color of [
      ...SICILY_BIVARIATE_COLORS_V1,
      ...SICILY_UNIVARIATE_COLORS_V1,
    ]) {
      expect(contrastRatio(legendTextColor(color), color)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("keeps the nine-color palette separable under common CVD simulations", () => {
    for (const matrix of Object.values(COLOR_VISION_MATRICES)) {
      const simulated = SICILY_BIVARIATE_COLORS_V1.map((color) => simulate(color, matrix));
      expect(minimumPairDistance(simulated)).toBeGreaterThanOrEqual(20);
    }
  });

  it("preserves two visible grayscale directions while every state retains text", () => {
    const model = legendModel(variableById("spei_3"), variableById("utci_daymax_median"));
    const luminances = SICILY_BIVARIATE_COLORS_V1.map(displayLuminance);

    expect(Math.max(...luminances) - Math.min(...luminances)).toBeGreaterThanOrEqual(0.4);
    expect(model.cells.every(({ label, description }) => label.length > 0 && description.length > 0)).toBe(
      true,
    );
  });
});
