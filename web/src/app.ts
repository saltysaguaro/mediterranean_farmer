import { DevelopmentTileLoader, PointSampleLoader, fetchAvailability } from "./data";
import {
  pointClassPair,
  renderExplanatoryPanels,
  renderPointSample,
} from "./inspection";
import { renderLegend } from "./legend";
import { GlobalMap } from "./map";
import {
  ALL_MONTHS_MASK,
  MONTHS,
  formatPeriod,
  hexToMask,
  maskToMonths,
  monthsToMask,
  toggleMonth,
} from "./months";
import { APP_CONFIG, VARIABLES, variableById } from "./registry";
import {
  constraintsFromAvailability,
  parseUrlState,
  stateUrl,
  type StateConstraints,
} from "./state";
import type {
  AppState,
  Availability,
  CompatibilityRecord,
  LoadStatus,
  PointSample,
  VariableManifest,
} from "./types";

type HistoryMode = "push" | "replace" | "none";

function fallbackAvailability(): Availability {
  const years = Array.from(
    new Set(VARIABLES.flatMap(({ publication }) => publication.published_years)),
  ).sort();
  return {
    status: "ok",
    dataset_version: APP_CONFIG.service.dataset_version,
    fixture: false,
    official_evidence: false,
    scope:
      "Registry-only fallback; the local data service is unavailable and no climate map is claimed.",
    maximum_active_variables: APP_CONFIG.maximum_active_variables,
    latest_complete_year: null,
    years: years.map((year) => ({
      year,
      months: Array.from({ length: 12 }, (_, index) => index + 1),
      complete: false,
      regions: [],
    })),
    variables: VARIABLES.map((variable) => ({
      id: variable.id,
      label: variable.label,
      unit: variable.unit,
      data_version: variable.publication.data_version,
      published_years: variable.publication.published_years,
    })),
    compatibility: [
      {
        variables: [VARIABLES[0].id, VARIABLES[1].id],
        compatible: true,
        reason: null,
      },
    ],
  };
}

function defaultState(availability: Availability): AppState {
  const latestYear =
    availability.latest_complete_year ??
    availability.years.map(({ year }) => year).sort((left, right) => right - left)[0];
  if (latestYear === undefined) {
    throw new Error("No published development year is available.");
  }
  const availableMonths =
    availability.years.find(({ year }) => year === latestYear)?.months ?? [];
  const availableMask = monthsToMask(availableMonths);
  const configuredMask = hexToMask(APP_CONFIG.default_view.month_mask);
  return {
    xVariable: APP_CONFIG.default_view.x_variable,
    yVariable: APP_CONFIG.default_view.y_variable,
    year: latestYear,
    monthMask: configuredMask & availableMask || availableMask,
    view: {
      longitude: 12.5,
      latitude: 18,
      zoom: 1.1,
    },
  };
}

function option(variable: VariableManifest, selected: boolean): HTMLOptionElement {
  const element = document.createElement("option");
  element.value = variable.id;
  element.textContent = `${variable.label} · ${variable.unit}`;
  element.selected = selected;
  return element;
}

function compatibleRecord(
  records: CompatibilityRecord[],
  left: string,
  right: string,
): CompatibilityRecord | undefined {
  return records.find(({ variables }) => {
    const ids = new Set(variables);
    return ids.has(left) && ids.has(right);
  });
}

function scopeLabel(availability: Availability): string {
  if (availability.fixture) {
    return "Deterministic interface fixture — not climate observations";
  }
  if (availability.official_evidence) {
    return "Bounded official sample — not global coverage";
  }
  return "Registry-only fallback — no climate map loaded";
}

function selectedCount(mask: number): number {
  return maskToMonths(mask).length;
}

export async function startApplication(root: HTMLElement): Promise<() => void> {
  root.innerHTML = `
    <div class="app-shell">
      <section class="map-stage" aria-labelledby="map-title">
        <div class="map-heading">
          <p class="eyebrow">Outdoor thermal conditions × drought</p>
          <h1 id="map-title">${APP_CONFIG.title}</h1>
          <p class="map-period" id="map-period"></p>
        </div>
        <div class="map-reference" aria-hidden="true">
          <div id="reference-markers" class="reference-markers"></div>
        </div>
        <div id="global-map" class="global-map" aria-label="Global climate map"></div>
        <div class="map-status" id="map-status" role="status" aria-live="polite">
          <span>Connecting to the bounded local data service.</span>
          <button class="retry-button" id="retry-map" type="button" hidden>Retry</button>
        </div>
        <p class="scope-badge" id="scope-badge"></p>
      </section>

      <details class="control-panel" open>
        <summary>Map controls</summary>
        <div class="control-panel__body">
          <header class="control-header">
            <p class="eyebrow">Analysis controls</p>
            <h2>Compare one or two variables</h2>
            <p>Selected-year monthly medians. No suitability scores.</p>
          </header>

          <fieldset class="axis-controls">
            <legend>Map variables</legend>
            <label for="x-variable">Axis X</label>
            <select id="x-variable"></select>
            <label for="y-variable">Axis Y</label>
            <select id="y-variable"></select>
            <button id="swap-axes" class="secondary-button" type="button">Swap axes</button>
            <p id="mode-summary" class="control-note"></p>
          </fieldset>

          <label class="year-control" for="analysis-year">
            Analysis year
            <select id="analysis-year"></select>
          </label>

          <fieldset class="month-control" aria-describedby="period-summary month-guidance">
            <legend>Months</legend>
            <p id="month-guidance" class="control-note">
              Toggle any published months. At least one must remain selected.
            </p>
            <div class="month-ring" aria-label="Circular month selector">
              <div id="month-buttons" class="month-ring__buttons"></div>
              <button id="all-months" class="month-ring__center" type="button"></button>
            </div>
            <p id="period-summary" class="period-summary"></p>
            <details class="month-list-fallback">
              <summary>Use the month checklist</summary>
              <div id="month-checkboxes" class="month-checkboxes"></div>
            </details>
          </fieldset>

          <section class="legend-panel" aria-labelledby="legend-heading">
            <p class="eyebrow">Interpretation</p>
            <h3 id="legend-heading">Fixed class legend</h3>
            <div id="legend-content"></div>
          </section>

          <section class="inspection-panel" aria-labelledby="inspection-heading">
            <p class="eyebrow">Point inspection</p>
            <h3 id="inspection-heading">Grid-cell readout</h3>
            <p class="control-note">
              Click or tap the map. Keyboard users can focus the map and press Enter or Space.
            </p>
            <button id="inspect-center" class="secondary-button inspection-button" type="button">
              Inspect map center
            </button>
            <div class="point-status" id="point-status" role="status" aria-live="polite">
              <span>Select a map coordinate to inspect.</span>
              <button class="retry-button" id="retry-point" type="button" hidden>Retry readout</button>
            </div>
            <div id="point-content" class="point-content">
              <p>No grid-cell value is selected. The map remains fully usable.</p>
            </div>
          </section>

          <section class="information-panels" aria-label="Data interpretation information">
            <details open>
              <summary>Sources and versions</summary>
              <div id="sources-content" class="information-content"></div>
            </details>
            <details>
              <summary>Methodology and temporal semantics</summary>
              <div id="methodology-content" class="information-content"></div>
            </details>
            <details>
              <summary>Limitations</summary>
              <div id="limitations-content" class="information-content"></div>
            </details>
          </section>

          <p id="selection-message" class="selection-message" aria-live="assertive"></p>
          <p class="sample-disclosure" id="sample-disclosure"></p>
        </div>
      </details>
    </div>
  `;

  const apiBase = APP_CONFIG.service.development_api_base;
  let availability: Availability;
  let availabilityWarning: string | null = null;
  try {
    availability = await fetchAvailability(apiBase);
  } catch (error) {
    availability = fallbackAvailability();
    availabilityWarning =
      error instanceof Error
        ? `Availability service unavailable: ${error.message}`
        : "Availability service unavailable.";
  }
  if (
    availability.maximum_active_variables !== APP_CONFIG.maximum_active_variables ||
    availability.maximum_active_variables !== 2
  ) {
    throw new Error("The UI and service must both cap active variables at exactly two.");
  }
  if (availability.years.length === 0) {
    root.innerHTML = `
      <section class="fatal-error" aria-labelledby="empty-heading">
        <p class="eyebrow">Published-data state</p>
        <h1 id="empty-heading">No analysis year is available</h1>
        <p>The service published no complete or partial year. No climate value or zero has been substituted.</p>
        <button id="retry-empty" class="secondary-button" type="button">Retry availability</button>
      </section>
    `;
    root.querySelector<HTMLButtonElement>("#retry-empty")!.addEventListener("click", () =>
      window.location.reload(),
    );
    return () => undefined;
  }

  const constraints: StateConstraints = constraintsFromAvailability(
    availability,
    APP_CONFIG.service.maximum_zoom,
  );
  const baseline = defaultState(availability);
  const initial = parseUrlState(new URL(window.location.href), baseline, constraints);
  let state = initial.state;

  const mapElement = root.querySelector<HTMLElement>("#global-map")!;
  const referenceMarkers = root.querySelector<HTMLElement>("#reference-markers")!;
  const periodElement = root.querySelector<HTMLElement>("#map-period")!;
  const statusElement = root.querySelector<HTMLElement>("#map-status span")!;
  const retryButton = root.querySelector<HTMLButtonElement>("#retry-map")!;
  const scopeBadge = root.querySelector<HTMLElement>("#scope-badge")!;
  const xSelect = root.querySelector<HTMLSelectElement>("#x-variable")!;
  const ySelect = root.querySelector<HTMLSelectElement>("#y-variable")!;
  const swapButton = root.querySelector<HTMLButtonElement>("#swap-axes")!;
  const modeSummary = root.querySelector<HTMLElement>("#mode-summary")!;
  const yearSelect = root.querySelector<HTMLSelectElement>("#analysis-year")!;
  const monthButtonsRoot = root.querySelector<HTMLElement>("#month-buttons")!;
  const monthCheckboxesRoot = root.querySelector<HTMLElement>("#month-checkboxes")!;
  const allMonthsButton = root.querySelector<HTMLButtonElement>("#all-months")!;
  const periodSummary = root.querySelector<HTMLElement>("#period-summary")!;
  const legendContent = root.querySelector<HTMLElement>("#legend-content")!;
  const inspectCenterButton = root.querySelector<HTMLButtonElement>("#inspect-center")!;
  const pointStatus = root.querySelector<HTMLElement>("#point-status")!;
  const pointStatusText = root.querySelector<HTMLElement>("#point-status span")!;
  const retryPointButton = root.querySelector<HTMLButtonElement>("#retry-point")!;
  const pointContent = root.querySelector<HTMLElement>("#point-content")!;
  const sourcesContent = root.querySelector<HTMLElement>("#sources-content")!;
  const methodologyContent = root.querySelector<HTMLElement>("#methodology-content")!;
  const limitationsContent = root.querySelector<HTMLElement>("#limitations-content")!;
  const selectionMessage = root.querySelector<HTMLElement>("#selection-message")!;
  const disclosure = root.querySelector<HTMLElement>("#sample-disclosure")!;
  const panel = root.querySelector<HTMLDetailsElement>(".control-panel")!;

  xSelect.append(...VARIABLES.map((variable) => option(variable, variable.id === state.xVariable)));
  const noSecondVariable = document.createElement("option");
  noSecondVariable.value = "";
  noSecondVariable.textContent = "None — univariate map";
  ySelect.append(
    noSecondVariable,
    ...VARIABLES.map((variable) => option(variable, variable.id === state.yVariable)),
  );
  for (const { year, complete } of availability.years) {
    const yearOption = document.createElement("option");
    yearOption.value = String(year);
    yearOption.textContent = complete ? String(year) : `${year} · partial sample`;
    yearSelect.append(yearOption);
  }

  const monthButtons = new Map<number, HTMLButtonElement>();
  const monthCheckboxes = new Map<number, HTMLInputElement>();
  for (const [index, month] of MONTHS.entries()) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "month-wedge";
    button.style.setProperty("--month-index", String(index));
    button.dataset.month = String(month.number);
    button.setAttribute("aria-label", month.full);
    const label = document.createElement("span");
    label.textContent = month.short;
    button.append(label);
    monthButtonsRoot.append(button);
    monthButtons.set(month.number, button);

    const fallbackLabel = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = String(month.number);
    checkbox.dataset.month = String(month.number);
    fallbackLabel.append(checkbox, ` ${month.full}`);
    monthCheckboxesRoot.append(fallbackLabel);
    monthCheckboxes.set(month.number, checkbox);
  }

  scopeBadge.textContent = scopeLabel(availability);
  disclosure.textContent = availability.scope;
  if (availabilityWarning) {
    selectionMessage.textContent = availabilityWarning;
  } else if (initial.warnings.length) {
    selectionMessage.textContent = initial.warnings.join(" ");
  }

  let inspectedCoordinate: { longitude: number; latitude: number } | null = null;
  let currentPointSample: PointSample | null = null;
  let pointSampleStale = false;
  const globalMap = new GlobalMap(
    mapElement,
    referenceMarkers,
    state.view,
    (view) => {
      state = { ...state, view };
      window.history.replaceState(state, "", stateUrl(state, new URL(window.location.href)));
    },
    (longitude, latitude) => inspectPoint(longitude, latitude),
  );
  const tileLoader = new DevelopmentTileLoader(
    apiBase,
    availability.dataset_version,
    {
      onStatus(loadStatus) {
        renderLoadStatus(loadStatus);
      },
      onData(payload) {
        globalMap.show(payload);
        disclosure.textContent = payload.scope;
      },
    },
  );
  const pointLoader = new PointSampleLoader(apiBase, {
    onStatus(loadStatus) {
      renderPointStatus(loadStatus);
    },
    onData(payload) {
      currentPointSample = payload;
      pointSampleStale = false;
      renderPointSample(pointContent, payload);
      globalMap.highlight(payload);
      renderCurrentLegend();
    },
  });

  function availableMonths(): number[] {
    return [...(constraints.monthsByYear.get(state.year) ?? [])];
  }

  function pairReason(left: string, right: string): string | null {
    const record = compatibleRecord(availability.compatibility, left, right);
    return record && !record.compatible
      ? record.reason ?? "The variables are not compatible."
      : null;
  }

  function selectedVariables(): VariableManifest[] {
    const variables = [variableById(state.xVariable)];
    if (state.yVariable) {
      variables.push(variableById(state.yVariable));
    }
    return variables;
  }

  function renderCurrentLegend(): void {
    const [xVariable, yVariable] = selectedVariables();
    const selected =
      currentPointSample && !pointSampleStale ? pointClassPair(currentPointSample) : null;
    renderLegend(
      legendContent,
      xVariable,
      yVariable ?? null,
      selected,
      (pair) => globalMap.emphasize(pair),
    );
  }

  function renderPointStatus(loadStatus: LoadStatus): void {
    pointStatusText.textContent = loadStatus.message;
    pointStatus.dataset.state = loadStatus.kind;
    retryPointButton.hidden = loadStatus.kind !== "error";
    pointSampleStale =
      loadStatus.hasLastValidMap &&
      (loadStatus.kind === "updating" || loadStatus.kind === "error");
    pointContent.dataset.stale = String(pointSampleStale);
    if (pointSampleStale) {
      globalMap.highlight(null);
      renderCurrentLegend();
    }
  }

  function inspectPoint(longitude: number, latitude: number): void {
    inspectedCoordinate = { longitude, latitude };
    pointLoader.load(state, longitude, latitude);
  }

  function syncControls(): void {
    xSelect.value = state.xVariable;
    ySelect.value = state.yVariable ?? "";
    yearSelect.value = String(state.year);
    swapButton.disabled = state.yVariable === null;

    for (const candidate of Array.from(ySelect.options)) {
      if (!candidate.value) {
        candidate.disabled = false;
        candidate.title = "";
        continue;
      }
      const reason =
        candidate.value === state.xVariable
          ? "Already selected on Axis X."
          : pairReason(state.xVariable, candidate.value);
      candidate.disabled = reason !== null;
      candidate.title = reason ?? "";
    }

    const xVariable = variableById(state.xVariable);
    const yVariable = state.yVariable ? variableById(state.yVariable) : null;
    modeSummary.textContent = yVariable
      ? `Bivariate: ${xVariable.short_label} on X and ${yVariable.short_label} on Y.`
      : `Univariate: ${xVariable.short_label}.`;

    const available = new Set(availableMonths());
    for (const month of MONTHS) {
      const selected = (state.monthMask & (1 << (month.number - 1))) !== 0;
      const disabled = !available.has(month.number);
      const button = monthButtons.get(month.number)!;
      button.disabled = disabled;
      button.setAttribute("aria-pressed", String(selected));
      button.title = disabled ? `${month.full} is not published in this bounded sample.` : "";
      const checkbox = monthCheckboxes.get(month.number)!;
      checkbox.disabled = disabled;
      checkbox.checked = selected;
    }

    const availableMask = monthsToMask([...available]);
    const allYearAvailable = availableMask === ALL_MONTHS_MASK;
    allMonthsButton.disabled = state.monthMask === availableMask;
    allMonthsButton.textContent =
      state.monthMask === availableMask
        ? allYearAvailable
          ? "All year"
          : "All available"
        : allYearAvailable
          ? "Select all year"
          : "Select all available";
    const count = selectedCount(state.monthMask);
    allMonthsButton.setAttribute(
      "aria-label",
      allYearAvailable ? "Select all twelve months" : "Select every published sample month",
    );
    periodSummary.textContent = `${formatPeriod(state.monthMask)} · ${count} ${
      count === 1 ? "month" : "months"
    }`;
    periodElement.textContent = `${state.year} · ${formatPeriod(state.monthMask)} · ${
      yVariable
        ? `${xVariable.short_label} × ${yVariable.short_label}`
        : xVariable.short_label
    }`;
    document.title = `${formatPeriod(state.monthMask)} ${state.year} · ${APP_CONFIG.title}`;
    renderCurrentLegend();
    renderExplanatoryPanels(
      sourcesContent,
      methodologyContent,
      limitationsContent,
      selectedVariables(),
    );
  }

  function renderLoadStatus(loadStatus: LoadStatus): void {
    statusElement.textContent = loadStatus.message;
    statusElement.parentElement!.dataset.state = loadStatus.kind;
    retryButton.hidden = loadStatus.kind !== "error";
  }

  function commit(next: AppState, historyMode: HistoryMode, loadMap = true): void {
    state = next;
    syncControls();
    globalMap.setView(state.view);
    if (historyMode !== "none") {
      const url = stateUrl(state, new URL(window.location.href));
      if (historyMode === "push") {
        window.history.pushState(state, "", url);
      } else {
        window.history.replaceState(state, "", url);
      }
    }
    if (loadMap) {
      tileLoader.load(state);
      if (inspectedCoordinate) {
        pointLoader.load(
          state,
          inspectedCoordinate.longitude,
          inspectedCoordinate.latitude,
        );
      }
    }
  }

  function applyMonthToggle(month: number): void {
    const result = toggleMonth(state.monthMask, month);
    selectionMessage.textContent = result.announcement ?? "";
    if (result.changed) {
      commit({ ...state, monthMask: result.mask }, "push");
    } else {
      syncControls();
    }
  }

  for (const button of monthButtons.values()) {
    button.addEventListener("click", () => applyMonthToggle(Number(button.dataset.month)));
  }
  for (const checkbox of monthCheckboxes.values()) {
    checkbox.addEventListener("change", () =>
      applyMonthToggle(Number(checkbox.dataset.month)),
    );
  }
  allMonthsButton.addEventListener("click", () => {
    selectionMessage.textContent = "";
    commit({ ...state, monthMask: monthsToMask(availableMonths()) }, "push");
  });
  xSelect.addEventListener("change", () => {
    const previousX = state.xVariable;
    const nextX = xSelect.value;
    const nextY = state.yVariable === nextX ? previousX : state.yVariable;
    commit({ ...state, xVariable: nextX, yVariable: nextY }, "push");
  });
  ySelect.addEventListener("change", () => {
    commit({ ...state, yVariable: ySelect.value || null }, "push");
  });
  swapButton.addEventListener("click", () => {
    if (!state.yVariable) {
      return;
    }
    commit(
      {
        ...state,
        xVariable: state.yVariable,
        yVariable: state.xVariable,
      },
      "push",
    );
  });
  yearSelect.addEventListener("change", () => {
    const year = Number(yearSelect.value);
    const nextAvailableMask = monthsToMask(constraints.monthsByYear.get(year) ?? []);
    const monthMask = state.monthMask & nextAvailableMask || nextAvailableMask;
    commit({ ...state, year, monthMask }, "push");
  });
  retryButton.addEventListener("click", () => tileLoader.retry(state));
  inspectCenterButton.addEventListener("click", () =>
    inspectPoint(state.view.longitude, state.view.latitude),
  );
  retryPointButton.addEventListener("click", () => {
    if (inspectedCoordinate) {
      inspectPoint(inspectedCoordinate.longitude, inspectedCoordinate.latitude);
    }
  });
  panel.addEventListener("toggle", () => window.setTimeout(() => globalMap.resize(), 0));

  const popStateListener = () => {
    const parsed = parseUrlState(new URL(window.location.href), baseline, constraints);
    selectionMessage.textContent = parsed.warnings.join(" ");
    commit(parsed.state, "none");
  };
  window.addEventListener("popstate", popStateListener);

  commit(state, "replace");

  return () => {
    window.removeEventListener("popstate", popStateListener);
    tileLoader.dispose();
    pointLoader.dispose();
    globalMap.dispose();
  };
}
