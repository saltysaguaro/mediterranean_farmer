import type { ClassPair } from "./legend";
import { formatPeriod } from "./months";
import { SCOPE_CONFIG } from "./registry";
import type { PointSample, PointVariableRecord, VariableManifest } from "./types";

function number(value: number): string {
  return Number(value.toFixed(4)).toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function retrievalDate(value: string | null): string {
  if (!value) {
    return "Not yet retrieved";
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
      ...term("Source retrieved", retrievalDate(variable.source.sample_retrieved_at)),
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
  description.textContent = `${variable.source.provider} · product v${variable.source.product_version}.`;
  const links = document.createElement("p");
  links.className = "source-links";
  const doi = document.createElement("a");
  doi.href = `https://doi.org/${variable.source.doi}`;
  doi.textContent = `DOI ${variable.source.doi}`;
  doi.target = "_blank";
  doi.rel = "noreferrer";
  const license = document.createElement("a");
  license.href = variable.source.license_url;
  license.textContent = variable.source.license;
  license.target = "_blank";
  license.rel = "noreferrer";
  links.append(doi, license);
  const update = document.createElement("p");
  update.textContent = variable.publication.sample_retrieved_at
    ? `Sicily release retrieved ${retrievalDate(variable.publication.sample_retrieved_at)}. Data version ${variable.publication.data_version}.`
    : `Sicily release is planned but not yet retrieved. Target data version ${variable.publication.data_version}.`;
  card.append(title, description, links, update);
  return card;
}

function boundaryCard(): HTMLElement {
  const source = SCOPE_CONFIG.boundary_source;
  const card = document.createElement("article");
  const title = document.createElement("h4");
  const dataset = document.createElement("a");
  dataset.href = source.dataset_url;
  dataset.textContent = `${source.authority} regional boundary`;
  dataset.target = "_blank";
  dataset.rel = "noreferrer";
  title.append(dataset);
  const description = document.createElement("p");
  description.textContent = `${source.dataset}. Transformed to the documented 0.25° provider-cell-center mask.`;
  const license = document.createElement("a");
  license.href = source.license_url;
  license.textContent = source.license;
  license.target = "_blank";
  license.rel = "noreferrer";
  card.append(title, description, license);
  return card;
}

export function renderExplanatoryPanels(
  sourcesRoot: HTMLElement,
  methodologyRoot: HTMLElement,
  limitationsRoot: HTMLElement,
  variables: VariableManifest[],
): void {
  const attributionYear = Math.max(
    ...variables.map(({ publication }) =>
      publication.sample_retrieved_at
        ? new Date(publication.sample_retrieved_at).getUTCFullYear()
        : 0,
    ),
  );
  const attribution = document.createElement("p");
  attribution.className = "source-attribution";
  attribution.textContent =
    `Contains modified Copernicus Climate Change Service information ${attributionYear}. ` +
    "Neither the European Commission nor ECMWF is responsible for any use of this information.";
  sourcesRoot.replaceChildren(
    ...variables.map(sourceCard),
    boundaryCard(),
    attribution,
  );

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
  scope.textContent = `${selectedCount === 1 ? "This variable is" : "These variables are"} limited to Sicilia. Provider cells are included only when their center lies inside the official Istat 2026 regional boundary.`;
  const physical = document.createElement("p");
  physical.textContent =
    "The 0.25° ERA5 grid does not resolve coastlines, shade, buildings, urban heat islands, terrain-scale wind, personal activity, water demand, soil moisture, reservoirs, governance, or household water access. A grid cell may include surrounding sea.";
  const drought = document.createElement("p");
  drought.textContent =
    "SPEI-3 is a selected-year meteorological water-balance anomaly. A median over its 1991–2020 reference period is not presented or labeled as drought risk.";
  const islands = document.createElement("p");
  islands.textContent = SCOPE_CONFIG.limitations[1];
  limitationsRoot.append(scope, physical, islands, drought);
}
