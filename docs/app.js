const state = {
  manifest: null,
  manifestUrl: "./data/manifest.json",
  map: null,
  bounds: null,
  countryLayer: null,
  majorCitiesLayer: null,
  localCitiesLayer: null,
  displayLayer: null,
  currentGeoraster: null,
  currentDataRasterUrl: null,
  rasterCache: new Map(),
  renderToken: 0,
};

const controls = {
  cropSelect: document.getElementById("crop-select"),
  modeSelect: document.getElementById("mode-select"),
  layerSelect: document.getElementById("layer-select"),
  displayModeSelect: document.getElementById("display-mode-select"),
  yearSlider: document.getElementById("year-slider"),
  yearValue: document.getElementById("year-value"),
  yearField: document.getElementById("year-field"),
  resetViewButton: document.getElementById("reset-view"),
  title: document.getElementById("title"),
  subtitle: document.getElementById("subtitle"),
  sourcesList: document.getElementById("sources-list"),
  mapMode: document.getElementById("map-mode"),
  mapRange: document.getElementById("map-range"),
  legendTitle: document.getElementById("legend-title"),
  legendBody: document.getElementById("legend-body"),
};

const CONTINUOUS_STOPS = [
  [255, 247, 188],
  [254, 196, 79],
  [254, 153, 41],
  [217, 95, 14],
  [153, 52, 4],
];

const CATEGORICAL_STOPS = [
  "rgb(243, 240, 232)",
  "rgb(214, 196, 124)",
  "rgb(236, 154, 68)",
  "rgb(215, 95, 58)",
  "rgb(170, 56, 92)",
  "rgb(74, 74, 163)",
  "rgb(20, 78, 122)",
];

init().catch(handleRenderError);

async function init() {
  await loadManifest(state.manifestUrl);
  buildMap();
  bindEvents();
  await loadOverlays();
  await renderActiveRaster();
}

async function loadManifest(url) {
  state.manifestUrl = url;
  state.manifest = await fetchJson(url);
  controls.modeSelect.value = state.manifest.default_view.mode || "annual_climatology";
  controls.layerSelect.value = state.manifest.default_view.layer || "total_score";
  controls.displayModeSelect.value = state.manifest.default_view.display_mode || "categorical";
  setupText();
  setupCropSelector();
  setupYearSlider();
  syncVisibleControls();
}

function setupText() {
  controls.title.textContent = "Mediterranean Basin";
  controls.subtitle.textContent = "";
  controls.sourcesList.innerHTML = "";

  state.manifest.sources.forEach((source) => {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = source.title;
    item.appendChild(link);
    controls.sourcesList.appendChild(item);
  });
}

function setupCropSelector() {
  controls.cropSelect.innerHTML = "";
  state.manifest.available_crops.forEach((crop) => {
    const option = document.createElement("option");
    option.value = crop.crop_name;
    option.textContent = crop.display_name;
    option.disabled = !crop.has_outputs;
    option.dataset.manifestPath = crop.manifest_path || "";
    controls.cropSelect.appendChild(option);
  });
  controls.cropSelect.value = state.manifest.crop.name;
}

function setupYearSlider() {
  const totalLayer = state.manifest.annual_layers.total_score;
  const years = Object.keys(totalLayer.year_files).map(Number).sort((a, b) => a - b);
  controls.yearSlider.min = String(years[0]);
  controls.yearSlider.max = String(years[years.length - 1]);
  controls.yearSlider.step = "1";
  if (!years.includes(Number(controls.yearSlider.value))) {
    controls.yearSlider.value = String(years[years.length - 1]);
  }
  controls.yearValue.textContent = controls.yearSlider.value;
}

function buildMap() {
  const [west, south, east, north] = state.manifest.bounds;
  state.bounds = L.latLngBounds([[south, west], [north, east]]);
  state.map = L.map("map", {
    crs: L.CRS.EPSG4326,
    zoomControl: true,
    attributionControl: false,
    preferCanvas: true,
    minZoom: 3,
  });

  createPane("suitability-pane", 260);
  createPane("boundary-pane", 360);
  createPane("label-pane", 420);

  state.map.fitBounds(state.bounds, { padding: [18, 18] });
  state.map.on("zoomend", () => {
    updateCityVisibility();
  });
  state.map.on("click", handleMapClick);
}

function createPane(name, zIndex) {
  state.map.createPane(name);
  const pane = state.map.getPane(name);
  pane.style.zIndex = String(zIndex);
}

function bindEvents() {
  controls.cropSelect.addEventListener("change", handleCropChange);
  controls.modeSelect.addEventListener("change", () => {
    syncVisibleControls();
    requestRender();
  });
  controls.layerSelect.addEventListener("change", requestRender);
  controls.displayModeSelect.addEventListener("change", requestRender);
  controls.yearSlider.addEventListener("input", () => {
    controls.yearValue.textContent = controls.yearSlider.value;
    requestRender();
  });
  controls.yearSlider.addEventListener("change", requestRender);
  controls.resetViewButton.addEventListener("click", resetView);
}

function syncVisibleControls() {
  controls.yearField.style.display = controls.modeSelect.value === "yearly" ? "grid" : "none";
  controls.yearValue.textContent = controls.yearSlider.value;
}

async function handleCropChange() {
  const selected = controls.cropSelect.selectedOptions[0];
  const manifestPath = selected.dataset.manifestPath;
  if (!manifestPath || selected.value === state.manifest.crop.name) {
    controls.cropSelect.value = state.manifest.crop.name;
    return;
  }

  const priorView = captureControlState();
  state.rasterCache.clear();
  await loadManifest(manifestPath);
  restoreControlState(priorView);
  await renderActiveRaster();
}

function captureControlState() {
  return {
    mode: controls.modeSelect.value,
    layer: controls.layerSelect.value,
    displayMode: controls.displayModeSelect.value,
    year: controls.yearSlider.value,
  };
}

function restoreControlState(viewState) {
  if (!viewState) return;
  if ([...controls.modeSelect.options].some((option) => option.value === viewState.mode)) {
    controls.modeSelect.value = viewState.mode;
  }
  if ([...controls.layerSelect.options].some((option) => option.value === viewState.layer)) {
    controls.layerSelect.value = viewState.layer;
  }
  if ([...controls.displayModeSelect.options].some((option) => option.value === viewState.displayMode)) {
    controls.displayModeSelect.value = viewState.displayMode;
  }
  const year = Number(viewState.year);
  const minYear = Number(controls.yearSlider.min);
  const maxYear = Number(controls.yearSlider.max);
  if (Number.isFinite(year) && year >= minYear && year <= maxYear) {
    controls.yearSlider.value = String(year);
  }
  syncVisibleControls();
}

async function loadOverlays() {
  const overlays = state.manifest.overlays;
  const [citiesData, countriesData] = await Promise.all([
    fetchJson(overlays.cities),
    overlays.countries ? fetchJson(overlays.countries).catch(() => null) : Promise.resolve(null),
  ]);

  if (countriesData) {
    state.countryLayer = L.geoJSON(countriesData, {
      pane: "boundary-pane",
      style: {
        color: "#75644d",
        weight: 0.8,
        opacity: 0.45,
        fillOpacity: 0,
      },
    }).addTo(state.map);
  }

  const majorMarkers = [];
  const localMarkers = [];
  citiesData.features.forEach((feature) => {
    const [lng, lat] = feature.geometry.coordinates;
    const tier = feature.properties.tier || "local";
    const marker = L.marker([lat, lng], {
      pane: "label-pane",
      interactive: false,
      icon: L.divIcon({
        className: `city-label ${tier === "major" ? "major" : "local"}`,
        html: `<span>${feature.properties.name}</span>`,
      }),
    });
    if (tier === "major") {
      majorMarkers.push(marker);
    } else {
      localMarkers.push(marker);
    }
  });

  state.majorCitiesLayer = L.layerGroup(majorMarkers).addTo(state.map);
  state.localCitiesLayer = L.layerGroup(localMarkers);
  updateCityVisibility();
}

function updateCityVisibility() {
  if (!state.map || !state.localCitiesLayer) return;
  const zoom = state.map.getZoom();
  if (zoom >= 6) {
    if (!state.map.hasLayer(state.localCitiesLayer)) {
      state.localCitiesLayer.addTo(state.map);
    }
  } else if (state.map.hasLayer(state.localCitiesLayer)) {
    state.map.removeLayer(state.localCitiesLayer);
  }
}

async function renderActiveRaster() {
  const renderToken = ++state.renderToken;
  const rasterInfo = activeRasterInfo();
  state.currentDataRasterUrl = rasterInfo.dataUrl;

  if (state.displayLayer) {
    state.map.removeLayer(state.displayLayer);
  }

  if (rasterInfo.displayUrl) {
    state.currentGeoraster = null;
    state.displayLayer = L.imageOverlay(rasterInfo.displayUrl, state.bounds, {
      className: "score-overlay",
      pane: "suitability-pane",
      opacity: 1,
      interactive: false,
    });
  } else {
    const georaster = await loadGeoraster(rasterInfo.dataUrl);
    if (renderToken !== state.renderToken) return;
    state.currentGeoraster = georaster;
    const baseResolution = Math.round(Math.max(window.innerWidth, window.innerHeight) * window.devicePixelRatio);
    const categoricalMode = controls.displayModeSelect.value === "categorical";
    const nativeResolution = Math.max(georaster.width || 0, georaster.height || 0);
    const rasterResolution = categoricalMode
      ? Math.max(960, nativeResolution)
      : Math.max(640, Math.min(1280, baseResolution));
    state.displayLayer = new GeoRasterLayer({
      georaster,
      pane: "suitability-pane",
      opacity: 1,
      resolution: rasterResolution,
      resampleMethod: "nearest",
      pixelValuesToColorFn: (pixelValues) => rasterColor(
        pixelValues[0],
        georaster.noDataValue,
        rasterInfo.range,
        rasterInfo.breaks,
        controls.displayModeSelect.value,
      ),
    });
  }

  if (renderToken !== state.renderToken) return;
  state.displayLayer.addTo(state.map);
  controls.mapMode.textContent = rasterInfo.title;
  controls.mapRange.textContent = `${rasterInfo.label} · ${controls.displayModeSelect.value === "categorical" ? "fixed score bands" : formatRange(rasterInfo.range)} ${rasterInfo.unit}`;
  updateLegend(rasterInfo);
  warmDataRaster(rasterInfo.dataUrl);
}

function activeRasterInfo() {
  const layer = controls.layerSelect.value;
  const layerInfo = state.manifest.annual_layers[layer];
  const mode = controls.modeSelect.value;
  const year = controls.yearSlider.value;
  if (mode === "yearly") {
    const yearDisplayFiles = layerInfo.year_display_files || {};
    return {
      title: `${layerInfo.label} · ${year}`,
      label: layerInfo.label,
      dataUrl: layerInfo.year_files[year],
      displayUrl: yearDisplayFiles[year] ? yearDisplayFiles[year][controls.displayModeSelect.value] : null,
      unit: layerInfo.unit,
      range: layerInfo.display_range,
      breaks: layerInfo.categorical_breaks || [],
    };
  }
  return {
    title: `30-Year ${layerInfo.label}`,
    label: layerInfo.label,
    dataUrl: layerInfo.climatology_file,
    displayUrl: layerInfo.climatology_display_files ? layerInfo.climatology_display_files[controls.displayModeSelect.value] : null,
    unit: layerInfo.unit,
    range: layerInfo.display_range,
    breaks: layerInfo.categorical_breaks || [],
  };
}

function updateLegend(rasterInfo) {
  controls.legendBody.innerHTML = "";
  if (controls.displayModeSelect.value === "categorical") {
    controls.legendTitle.textContent = `${rasterInfo.label} score bands`;
    buildCategoricalLegend(rasterInfo.range, rasterInfo.breaks);
    return;
  }

  controls.legendTitle.textContent = `${rasterInfo.label} continuous scale`;
  const gradient = document.createElement("div");
  gradient.className = "legend-gradient";
  controls.legendBody.appendChild(gradient);

  const labels = document.createElement("div");
  labels.className = "legend-labels";
  labels.innerHTML = `<span>${formatTick(rasterInfo.range[0])}</span><span>${formatTick(rasterInfo.range[1])}</span>`;
  controls.legendBody.appendChild(labels);
}

function buildCategoricalLegend(range, breaks) {
  const thresholds = [range[0], ...breaks, range[1]];
  thresholds.slice(0, -1).forEach((start, index) => {
    const end = thresholds[index + 1];
    const item = document.createElement("div");
    item.className = "legend-item";

    const swatch = document.createElement("span");
    swatch.className = "legend-swatch";
    swatch.style.background = CATEGORICAL_STOPS[Math.min(index, CATEGORICAL_STOPS.length - 1)];

    const label = document.createElement("span");
    label.textContent = formatCategoricalLabel(index, start, end, thresholds.length - 2);

    item.appendChild(swatch);
    item.appendChild(label);
    controls.legendBody.appendChild(item);
  });
}

function resetView() {
  state.map.fitBounds(state.bounds, { padding: [18, 18] });
}

async function handleMapClick(event) {
  const info = activeRasterInfo();
  const georaster = await activeGeoraster();
  if (!georaster) return;
  const selectedCell = sampleGeorasterCell(georaster, event.latlng.lng, event.latlng.lat);
  if (!selectedCell) return;

  const details = await sampleAnnualDetails(selectedCell.centerLat, selectedCell.centerLng);
  const rows = [
    `<div><strong>Layer:</strong> ${info.label}</div>`,
    `<div><strong>Selected value:</strong> ${formatValue(selectedCell.value)}</div>`,
    `<div><strong>Grid center:</strong> ${selectedCell.centerLat.toFixed(4)}, ${selectedCell.centerLng.toFixed(4)}</div>`,
  ];

  if (controls.modeSelect.value === "yearly") {
    rows.push(`<div><strong>Year:</strong> ${controls.yearSlider.value}</div>`);
  } else {
    rows.push("<div><strong>View:</strong> 30-year annual climatology</div>");
  }

  if (details.total_score != null) rows.push(`<div><strong>Total score:</strong> ${formatValue(details.total_score)}</div>`);
  if (details.temperature_score != null) rows.push(`<div><strong>Temperature score:</strong> ${formatValue(details.temperature_score)}</div>`);
  if (details.precipitation_score != null) rows.push(`<div><strong>Precipitation score:</strong> ${formatValue(details.precipitation_score)}</div>`);
  if (details.humidity_score != null) rows.push(`<div><strong>Humidity score:</strong> ${formatValue(details.humidity_score)}</div>`);

  L.popup()
    .setLatLng(event.latlng)
    .setContent(`<div class="popup-title">${info.title}</div><div class="popup-grid">${rows.join("")}</div>`)
    .openOn(state.map);
}

async function sampleAnnualDetails(lat, lng) {
  const layerKeys = ["total_score", "temperature_score", "precipitation_score", "humidity_score"];
  const details = {};
  await Promise.all(
    layerKeys.map(async (key) => {
      const layerInfo = state.manifest.annual_layers[key];
      const url = controls.modeSelect.value === "yearly"
        ? layerInfo.year_files[controls.yearSlider.value]
        : layerInfo.climatology_file;
      const georaster = await loadGeoraster(url);
      const cell = sampleGeorasterCell(georaster, lng, lat);
      details[key] = cell ? cell.value : null;
    }),
  );
  return details;
}

function sampleGeorasterCell(georaster, lng, lat) {
  const { xmin, ymax, pixelWidth, pixelHeight, width, height, noDataValue, values } = georaster;
  const col = Math.floor((lng - xmin) / pixelWidth);
  const row = Math.floor((ymax - lat) / pixelHeight);
  if (row < 0 || col < 0 || row >= height || col >= width) {
    return null;
  }
  const value = values[0][row][col];
  if (value == null || Number.isNaN(value)) return null;
  if (noDataValue != null && value === noDataValue) return null;
  if (value <= -9998) return null;
  return {
    value,
    row,
    col,
    centerLng: xmin + (col + 0.5) * pixelWidth,
    centerLat: ymax - (row + 0.5) * pixelHeight,
  };
}

async function activeGeoraster() {
  const url = state.currentDataRasterUrl || activeRasterInfo().dataUrl;
  if (!url) return null;
  if (state.currentGeoraster && state.rasterCache.get(url) === state.currentGeoraster) {
    return state.currentGeoraster;
  }
  const georaster = await loadGeoraster(url);
  state.currentGeoraster = georaster;
  return georaster;
}

async function loadGeoraster(url) {
  if (state.rasterCache.has(url)) {
    return state.rasterCache.get(url);
  }
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Unable to fetch raster ${url}: ${response.status}`);
  }
  const buffer = await response.arrayBuffer();
  const georaster = await parseGeoraster(buffer);
  state.rasterCache.set(url, georaster);
  return georaster;
}

function warmDataRaster(url) {
  if (!url || state.rasterCache.has(url)) return;
  const preload = () => {
    loadGeoraster(url).catch(() => {});
  };
  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(preload, { timeout: 1200 });
    return;
  }
  window.setTimeout(preload, 0);
}

function rasterColor(value, noDataValue, range, breaks, displayMode) {
  if (value == null || Number.isNaN(value)) return null;
  if (noDataValue != null && value === noDataValue) return null;
  if (value <= -9998) return null;
  if (displayMode === "categorical") {
    return categoricalColor(value, breaks);
  }
  const t = clamp((value - range[0]) / (range[1] - range[0] || 1), 0, 1);
  return interpolateColor(CONTINUOUS_STOPS, t);
}

function categoricalColor(value, breaks) {
  let index = 0;
  while (index < breaks.length && value > breaks[index]) {
    index += 1;
  }
  return CATEGORICAL_STOPS[Math.min(index, CATEGORICAL_STOPS.length - 1)];
}

function interpolateColor(stops, t) {
  if (t <= 0) return rgb(stops[0]);
  if (t >= 1) return rgb(stops[stops.length - 1]);
  const scaled = t * (stops.length - 1);
  const index = Math.floor(scaled);
  const localT = scaled - index;
  const a = stops[index];
  const b = stops[index + 1];
  return rgb([
    Math.round(a[0] + (b[0] - a[0]) * localT),
    Math.round(a[1] + (b[1] - a[1]) * localT),
    Math.round(a[2] + (b[2] - a[2]) * localT),
  ]);
}

function rgb([r, g, b]) {
  return `rgb(${r}, ${g}, ${b})`;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function formatValue(value) {
  return Number(value).toFixed(1);
}

function formatTick(value) {
  const numeric = Number(value);
  return numeric >= 100 ? numeric.toFixed(0) : numeric.toFixed(1);
}

function formatRange(range) {
  return `${formatTick(range[0])} to ${formatTick(range[1])}`;
}

function formatCategoricalLabel(index, start, end, lastIndex) {
  const lower = index === 0 ? start : start + 1;
  const label = `${formatTick(lower)} to ${formatTick(end)}`;
  return index === lastIndex ? `${label} (top band)` : label;
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Unable to fetch ${url}: ${response.status}`);
  }
  return response.json();
}

function requestRender() {
  renderActiveRaster().catch(handleRenderError);
}

function handleRenderError(error) {
  controls.subtitle.textContent = `Failed to load the map: ${error.message}`;
  console.error(error);
}
