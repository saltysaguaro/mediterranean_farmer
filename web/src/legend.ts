import type { VariableManifest } from "./types";

export const SICILY_BIVARIATE_COLORS_V1 = [
  "#d9f0d3",
  "#addd8e",
  "#78c679",
  "#c2e7df",
  "#8bc5c5",
  "#4a9eaa",
  "#d4c9e8",
  "#a89acb",
  "#756bb1",
] as const;

export const SICILY_UNIVARIATE_COLORS_V1 = ["#d9f0d3", "#78c679", "#238443"] as const;
export const NO_DATA_COLOR = "#5f6862";

export interface ClassPair {
  xClass: number;
  yClass: number | null;
}

export interface LegendCell extends ClassPair {
  color: string;
  label: string;
  description: string;
}

export interface LegendModel {
  mode: "univariate" | "bivariate";
  xLabel: string;
  yLabel: string | null;
  cells: LegendCell[];
}

function relativeLuminance(color: string): number {
  const channels = color
    .replace("#", "")
    .match(/.{2}/g)!
    .map((channel) => Number.parseInt(channel, 16) / 255)
    .map((channel) =>
      channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
    );
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

export function contrastRatio(foreground: string, background: string): number {
  const foregroundLuminance = relativeLuminance(foreground);
  const backgroundLuminance = relativeLuminance(background);
  return (
    (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) /
    (Math.min(foregroundLuminance, backgroundLuminance) + 0.05)
  );
}

export function legendTextColor(background: string): string {
  const dark = "#11221a";
  const light = "#ffffff";
  return contrastRatio(dark, background) >= contrastRatio(light, background) ? dark : light;
}

function displayOrder(variable: VariableManifest): number[] {
  return variable.classification.axis_display_order === "ascending"
    ? [0, 1, 2]
    : [2, 1, 0];
}

function threshold(value: number): string {
  return Number(value.toFixed(4)).toString();
}

export function classRange(variable: VariableManifest, classIndex: number): string {
  const [lowerBreak, upperBreak] = variable.classification.breaks;
  const [lowerAssignment, upperAssignment] = variable.classification.break_assignments;
  if (classIndex === 0) {
    return `${lowerAssignment === "lower_class" ? "≤" : "<"} ${threshold(lowerBreak)} ${variable.unit}`;
  }
  if (classIndex === 1) {
    const lowerOperator = lowerAssignment === "lower_class" ? ">" : "≥";
    const upperOperator = upperAssignment === "lower_class" ? "≤" : "<";
    return `${lowerOperator} ${threshold(lowerBreak)} and ${upperOperator} ${threshold(upperBreak)} ${variable.unit}`;
  }
  return `${upperAssignment === "lower_class" ? ">" : "≥"} ${threshold(upperBreak)} ${variable.unit}`;
}

export function colorForClasses(xClass: number | null, yClass: number | null): string {
  if (xClass === null) {
    return NO_DATA_COLOR;
  }
  if (yClass === null) {
    return SICILY_UNIVARIATE_COLORS_V1[xClass] ?? NO_DATA_COLOR;
  }
  return SICILY_BIVARIATE_COLORS_V1[yClass * 3 + xClass] ?? NO_DATA_COLOR;
}

export function legendModel(
  xVariable: VariableManifest,
  yVariable: VariableManifest | null,
): LegendModel {
  if (!yVariable) {
    return {
      mode: "univariate",
      xLabel: xVariable.label,
      yLabel: null,
      cells: displayOrder(xVariable).map((xClass) => ({
        xClass,
        yClass: null,
        color: colorForClasses(xClass, null),
        label: xVariable.classification.labels[xClass],
        description: classRange(xVariable, xClass),
      })),
    };
  }

  const cells: LegendCell[] = [];
  const xOrder = displayOrder(xVariable);
  const yBottomToTop = displayOrder(yVariable);
  for (const yClass of [...yBottomToTop].reverse()) {
    for (const xClass of xOrder) {
      const xLabel = xVariable.classification.labels[xClass];
      const yLabel = yVariable.classification.labels[yClass];
      cells.push({
        xClass,
        yClass,
        color: colorForClasses(xClass, yClass),
        label: `${xLabel} × ${yLabel}`,
        description: `${xVariable.short_label}: ${classRange(xVariable, xClass)}; ${yVariable.short_label}: ${classRange(yVariable, yClass)}`,
      });
    }
  }
  return {
    mode: "bivariate",
    xLabel: xVariable.label,
    yLabel: yVariable.label,
    cells,
  };
}

function samePair(left: ClassPair | null, right: ClassPair): boolean {
  return left?.xClass === right.xClass && left.yClass === right.yClass;
}

function axisKey(variable: VariableManifest, axisName: string): HTMLElement {
  const wrapper = document.createElement("div");
  wrapper.className = "legend-axis-key";
  const heading = document.createElement("h4");
  heading.textContent = `${axisName}: ${variable.label} (${variable.unit})`;
  const list = document.createElement("ul");
  for (const classIndex of displayOrder(variable)) {
    const item = document.createElement("li");
    item.textContent = `${variable.classification.labels[classIndex]} — ${classRange(variable, classIndex)}`;
    list.append(item);
  }
  wrapper.append(heading, list);
  return wrapper;
}

export function renderLegend(
  root: HTMLElement,
  xVariable: VariableManifest,
  yVariable: VariableManifest | null,
  selected: ClassPair | null,
  onEmphasis: (pair: ClassPair | null) => void,
): void {
  const model = legendModel(xVariable, yVariable);
  root.replaceChildren();
  root.dataset.mode = model.mode;

  const intro = document.createElement("p");
  intro.className = "legend-intro";
  intro.textContent =
    model.mode === "bivariate"
      ? "Every map color is one labeled X/Y class pair. Focus a cell to emphasize matching sample points."
      : "Each color is one fixed class; thresholds do not rescale with the selected period.";

  const cells = document.createElement("div");
  cells.className = model.mode === "bivariate" ? "bivariate-matrix" : "univariate-scale";
  cells.setAttribute("role", "group");
  cells.setAttribute(
    "aria-label",
    model.mode === "bivariate" ? "Nine bivariate class combinations" : "Three univariate classes",
  );
  for (const cell of model.cells) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "legend-cell";
    button.style.setProperty("--legend-color", cell.color);
    button.style.setProperty("--legend-text", legendTextColor(cell.color));
    button.dataset.xClass = String(cell.xClass);
    if (cell.yClass !== null) {
      button.dataset.yClass = String(cell.yClass);
    }
    button.setAttribute("aria-label", `${cell.label}. ${cell.description}`);
    if (samePair(selected, cell)) {
      button.classList.add("is-selected");
      button.setAttribute("aria-current", "true");
    }
    const label = document.createElement("span");
    label.className = "legend-cell__label";
    label.textContent = cell.label;
    const description = document.createElement("span");
    description.className = "legend-cell__range";
    description.textContent = cell.description;
    button.append(label, description);
    const pair = { xClass: cell.xClass, yClass: cell.yClass };
    button.addEventListener("pointerenter", () => onEmphasis(pair));
    button.addEventListener("pointerleave", () => onEmphasis(null));
    button.addEventListener("focus", () => onEmphasis(pair));
    button.addEventListener("blur", () => onEmphasis(null));
    cells.append(button);
  }

  const noData = document.createElement("div");
  noData.className = "no-data-key";
  const swatch = document.createElement("span");
  swatch.className = "no-data-swatch";
  swatch.setAttribute("aria-hidden", "true");
  const noDataText = document.createElement("span");
  noDataText.textContent = "No data or failed provider quality — outside the color matrix, never zero.";
  noData.append(swatch, noDataText);

  root.append(intro, cells, axisKey(xVariable, "Axis X"));
  if (yVariable) {
    root.append(axisKey(yVariable, "Axis Y"));
  }
  root.append(noData);
}
