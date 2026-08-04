import type { ClassPair } from "./legend";
import { formatPeriod } from "./months";
import type { PointSample, PointVariableRecord, VariableManifest } from "./types";

function number(value: number): string {
  return Number(value.toFixed(4)).toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function retrievalDate(value: string | null): string {
  if (!value) {
    return "not published";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(value));
}

export function qualityLabel(variable: PointVariableRecord): string {
  switch (variable.quality_state) {
    case "passes":
      return `Provider quality passed for ${variable.quality_pass_month_count} of ${variable.selected_month_count} selected months.`;
    case "partial_quality":
      return `Provider quality passed for only ${variable.quality_pass_month_count} of ${variable.selected_month_count} selected months.`;
    case "low_quality":
      return "Provider quality failed; the drought value remains no data.";
    case "not_applicable":
      return "No separate provider quality mask applies to this variable.";
    default:
      return "Provider quality was not evaluated outside the bounded sample.";
  }
}

export function pointClassPair(sample: PointSample): ClassPair | null {
  const xClass = sample.variables[0]?.class_index ?? null;
  if (xClass === null) {
    return null;
  }
  if (sample.variables.length === 1) {
    return { xClass, yClass: null };
  }
  const yClass = sample.variables[1]?.class_index ?? null;
  return yClass === null ? null : { xClass, yClass };
}

function term(label: string, value: string): HTMLElement[] {
  const name = document.createElement("dt");
  name.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value;
  return [name, description];
}

export function renderPointSample(root: HTMLElement, sample: PointSample): void {
  root.replaceChildren();
  const coordinate = sample.grid_cell ?? sample.requested_coordinate;
  const heading = document.createElement("h4");
  heading.textContent = sample.region_id
    ? `${sample.region_id.replaceAll("_", " ")} grid cell`
    : "Coordinate outside the bounded sample";
  const period = document.createElement("p");
  period.className = "inspection-period";
  period.textContent = `${number(coordinate.latitude)}°, ${number(coordinate.longitude)}° · ${sample.year} · ${formatPeriod(Number.parseInt(sample.month_mask, 16))}`;
  root.append(heading, period);

  if (sample.status === "no_data" && !sample.grid_cell) {
    const empty = document.createElement("p");
    empty.className = "point-empty";
    empty.textContent =
      "No published sample grid cell covers this coordinate. No value has been substituted.";
    root.append(empty);
  }

  for (const variable of sample.variables) {
    const card = document.createElement("article");
    card.className = "point-variable";
    const title = document.createElement("h5");
    title.textContent = variable.label;
    const values = document.createElement("dl");
    values.append(
      ...term(
        "Value",
        variable.value === null ? "No data" : `${number(variable.value)} ${variable.unit}`,
      ),
      ...term("Class", variable.class_label ?? "No data"),
      ...term(
        "Valid months",
        variable.selected_month_count === null
          ? "Not evaluated"
          : `${variable.valid_month_count} of ${variable.selected_month_count}; ${variable.required_valid_month_count} required`,
      ),
      ...term("Quality", qualityLabel(variable)),
      ...term(
        "Source",
        `${variable.source.dataset} v${variable.source.product_version}`,
      ),
      ...term("Sample retrieved", retrievalDate(variable.source.sample_retrieved_at)),
    );
    card.append(title, values);
    root.append(card);
  }

  const limitation = document.createElement("p");
  limitation.className = "grid-limitation";
  limitation.textContent =
    "These are 0.25° reanalysis grid-cell values, not the exact point, a personal exposure forecast, or a health outcome.";
  root.append(limitation);
}

function sourceCard(variable: VariableManifest): HTMLElement {
  const card = document.createElement("article");
  const title = document.createElement("h4");
  const link = document.createElement("a");
  link.href = variable.source.dataset_url;
  link.textContent = variable.source.dataset;
  link.target = "_blank";
  link.rel = "noreferrer";
  title.append(link);
  const description = document.createElement("p");
  description.textContent = `${variable.source.provider} · product v${variable.source.product_version} · DOI ${variable.source.doi} · ${variable.source.license}.`;
  const update = document.createElement("p");
  update.textContent = `Bounded sample retrieved ${retrievalDate(variable.publication.sample_retrieved_at)}. Data version ${variable.publication.data_version}.`;
  card.append(title, description, update);
  return card;
}

export function renderExplanatoryPanels(
  sourcesRoot: HTMLElement,
  methodologyRoot: HTMLElement,
  limitationsRoot: HTMLElement,
  variables: VariableManifest[],
): void {
  sourcesRoot.replaceChildren(...variables.map(sourceCard));

  const selectedCount = variables.length;
  methodologyRoot.replaceChildren();
  const temporal = document.createElement("p");
  temporal.textContent =
    "The selected months are calendar months in UTC and receive equal weight. Each map value is the median of the selected monthly layers; an even count uses the mean of the two center values.";
  const validity = document.createElement("p");
  validity.textContent =
    "A cell needs at least ceil(selected month count × 0.75) valid values, with a minimum of one. Missing and quality-masked values remain no data, never zero.";
  const semantics = document.createElement("ul");
  for (const variable of variables) {
    const item = document.createElement("li");
    item.textContent = `${variable.label}: ${variable.aggregation.temporal_note}`;
    semantics.append(item);
  }
  methodologyRoot.append(temporal, validity, semantics);

  limitationsRoot.replaceChildren();
  const scope = document.createElement("p");
  scope.textContent = `${selectedCount === 1 ? "This variable is" : "These variables are"} shown only for the four-region January/July 2024 development sample. Global navigation is not global published coverage.`;
  const physical = document.createElement("p");
  physical.textContent =
    "The 0.25° ERA5 grid does not resolve shade, buildings, urban heat islands, terrain-scale wind, personal activity, water demand, soil moisture, reservoirs, governance, or household water access. ERA5-HEAT stops at 60°S, so Antarctica is no data.";
  const drought = document.createElement("p");
  drought.textContent =
    "SPEI-3 is a selected-year meteorological water-balance anomaly. A median over its 1991–2020 reference period is not presented or labeled as drought risk.";
  limitationsRoot.append(scope, physical, drought);
}
