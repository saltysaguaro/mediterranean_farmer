import maplibregl, {
  type GeoJSONSource,
  type LngLatLike,
  type Map as MapLibreMap,
  type StyleSpecification,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { colorForClasses, NO_DATA_COLOR, type ClassPair } from "./legend";
import type { LosslessMapResponse, MapView, PointSample, ScopeConfiguration } from "./types";

type FeatureCollection = GeoJSON.FeatureCollection<GeoJSON.Point, CellProperties>;
interface CellProperties {
  color: string;
  emphasized: boolean;
  region: string;
  selected: boolean;
  summary: string;
}

function emptyStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {},
    layers: [
      {
        id: "background",
        type: "background",
        paint: { "background-color": "rgba(220, 232, 229, 0)" },
      },
    ],
  };
}

function colorForCell(payload: LosslessMapResponse, cellIndex: number): string {
  const variables = payload.cells[cellIndex].variables;
  if (variables.some(({ class_index: classIndex }) => classIndex === null)) {
    return NO_DATA_COLOR;
  }
  return colorForClasses(
    variables[0].class_index,
    variables.length === 1 ? null : variables[1].class_index,
  );
}

function tileFeatures(
  payload: LosslessMapResponse,
  selectedSample: PointSample | null,
  emphasizedPair: ClassPair | null,
): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: payload.cells.map((cell, index) => {
      const xClass = cell.variables[0]?.class_index ?? null;
      const yClass = cell.variables.length === 1 ? null : cell.variables[1]?.class_index ?? null;
      const emphasized =
        emphasizedPair === null ||
        (xClass === emphasizedPair.xClass && yClass === emphasizedPair.yClass);
      const selected =
        selectedSample?.grid_cell?.latitude === cell.latitude &&
        selectedSample.grid_cell.longitude === cell.longitude &&
        selectedSample.region_id === cell.region_id;
      return {
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [cell.longitude, cell.latitude],
        },
        properties: {
          color: colorForCell(payload, index),
          emphasized,
          region: cell.region_id,
          selected,
          summary: cell.variables
            .map(
              ({ label, value, class_label: classLabel, unit }) =>
                `${label}: ${value === null ? "no data" : `${value.toFixed(2)} ${unit}`} (${classLabel ?? "no data"})`,
            )
            .join(" · "),
        },
      };
    }),
  };
}

function graticule(scope: ScopeConfiguration): GeoJSON.FeatureCollection<GeoJSON.LineString> {
  const features: GeoJSON.Feature<GeoJSON.LineString>[] = [];
  const [west, south, east, north] = scope.map.bounds;
  for (let longitude = Math.ceil(west * 2) / 2; longitude <= east; longitude += 0.5) {
    features.push({
      type: "Feature",
      properties: {},
      geometry: {
        type: "LineString",
        coordinates: [
          [longitude, south],
          [longitude, north],
        ],
      },
    });
  }
  for (let latitude = Math.ceil(south * 2) / 2; latitude <= north; latitude += 0.5) {
    features.push({
      type: "Feature",
      properties: {},
      geometry: {
        type: "LineString",
        coordinates: [
          [west, latitude],
          [east, latitude],
        ],
      },
    });
  }
  return { type: "FeatureCollection", features };
}

function coverage(scope: ScopeConfiguration): GeoJSON.FeatureCollection<GeoJSON.Polygon> {
  const [west, south, east, north] = scope.analysis_grid.acquisition_bbox;
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { kind: "published-domain" },
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [west, south],
              [east, south],
              [east, north],
              [west, north],
              [west, south],
            ],
          ],
        },
      },
    ],
  };
}

export class ClimateMap {
  private readonly map: MapLibreMap;
  private pendingTile: LosslessMapResponse | null = null;
  private selectedSample: PointSample | null = null;
  private emphasizedPair: ClassPair | null = null;
  private ready = false;
  private suppressViewEvent = false;

  constructor(
    container: HTMLElement,
    private readonly referenceMarkers: HTMLElement,
    private readonly scope: ScopeConfiguration,
    initialView: MapView,
    onViewChange: (view: MapView) => void,
    onInspect: (longitude: number, latitude: number) => void,
  ) {
    this.map = new maplibregl.Map({
      container,
      style: emptyStyle(),
      center: [initialView.longitude, initialView.latitude],
      zoom: initialView.zoom,
      minZoom: scope.map.minimum_zoom,
      maxZoom: scope.map.maximum_zoom,
      maxBounds: [
        [scope.map.bounds[0], scope.map.bounds[1]],
        [scope.map.bounds[2], scope.map.bounds[3]],
      ],
      renderWorldCopies: false,
      attributionControl: false,
    });
    this.map.addControl(
      new maplibregl.NavigationControl({ showCompass: false, visualizePitch: false }),
      "top-right",
    );
    this.map.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution: "Sicily 0.25° grid · no external basemap",
      }),
      "bottom-right",
    );
    this.map.on("load", () => {
      this.ready = true;
      this.referenceMarkers.hidden = true;
      this.addReferenceLayers();
      if (this.pendingTile) {
        this.renderTile(this.pendingTile);
      }
      const canvas = this.map.getCanvas();
      canvas.setAttribute(
        "aria-label",
        "Sicily climate map. Use arrow keys to pan; press Enter or Space to inspect the map center.",
      );
      canvas.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") {
          return;
        }
        event.preventDefault();
        const center = this.map.getCenter();
        onInspect(center.lng, center.lat);
      });
    });
    this.map.on("click", (event) => {
      const feature = this.map.queryRenderedFeatures(event.point, {
        layers: this.ready ? ["sample-cells"] : [],
      })[0];
      if (feature?.geometry.type === "Point") {
        const [longitude, latitude] = feature.geometry.coordinates;
        onInspect(longitude, latitude);
        return;
      }
      onInspect(event.lngLat.lng, event.lngLat.lat);
    });
    this.map.on("moveend", () => {
      if (this.suppressViewEvent) {
        this.suppressViewEvent = false;
        return;
      }
      const center = this.map.getCenter();
      onViewChange({
        longitude: center.lng,
        latitude: center.lat,
        zoom: this.map.getZoom(),
      });
    });
  }

  show(payload: LosslessMapResponse): void {
    this.pendingTile = payload;
    if (this.ready) {
      this.renderTile(payload);
    }
  }

  highlight(sample: PointSample | null): void {
    this.selectedSample = sample;
    if (this.ready && this.pendingTile) {
      this.renderTile(this.pendingTile);
    }
  }

  emphasize(pair: ClassPair | null): void {
    this.emphasizedPair = pair;
    if (this.ready && this.pendingTile) {
      this.renderTile(this.pendingTile);
    }
  }

  setView(view: MapView): void {
    const center = this.map.getCenter();
    if (
      Math.abs(center.lng - view.longitude) < 0.0001 &&
      Math.abs(center.lat - view.latitude) < 0.0001 &&
      Math.abs(this.map.getZoom() - view.zoom) < 0.0001
    ) {
      return;
    }
    this.suppressViewEvent = true;
    this.map.jumpTo({
      center: [view.longitude, view.latitude] as LngLatLike,
      zoom: view.zoom,
    });
  }

  resize(): void {
    this.map.resize();
  }

  dispose(): void {
    this.map.remove();
  }

  private addReferenceLayers(): void {
    this.map.addSource("coverage", { type: "geojson", data: coverage(this.scope) });
    this.map.addLayer({
      id: "coverage",
      type: "fill",
      source: "coverage",
      paint: {
        "fill-color": "#c9ddd4",
        "fill-opacity": 0.58,
        "fill-outline-color": "#6f877b",
      },
    });
    this.map.addSource("graticule", { type: "geojson", data: graticule(this.scope) });
    this.map.addLayer({
      id: "graticule",
      type: "line",
      source: "graticule",
      paint: {
        "line-color": "#71837c",
        "line-opacity": 0.58,
        "line-width": 1,
      },
    });
    this.map.addSource("sample-cells", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
    this.map.addLayer({
      id: "sample-cells-halo",
      type: "circle",
      source: "sample-cells",
      paint: {
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["zoom"],
          0,
          ["case", ["get", "selected"], 9.5, 7],
          5,
          ["case", ["get", "selected"], 17.5, 13],
        ],
        "circle-color": ["case", ["get", "selected"], "#f4b942", "#ffffff"],
        "circle-opacity": ["case", ["get", "emphasized"], 1, 0.25],
        "circle-stroke-color": "#17221c",
        "circle-stroke-width": 1.5,
      },
    });
    this.map.addLayer({
      id: "sample-cells",
      type: "circle",
      source: "sample-cells",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 0, 5, 5, 11],
        "circle-color": ["get", "color"],
        "circle-opacity": ["case", ["get", "emphasized"], 1, 0.2],
      },
    });
  }

  private renderTile(payload: LosslessMapResponse): void {
    const source = this.map.getSource("sample-cells") as GeoJSONSource | undefined;
    source?.setData(tileFeatures(payload, this.selectedSample, this.emphasizedPair));
    this.referenceMarkers.replaceChildren(
      ...payload.cells.map((cell, index) => {
        const [west, south, east, north] = this.scope.map.bounds;
        const marker = document.createElement("span");
        marker.className = "reference-sample-marker";
        marker.style.left = `${((cell.longitude - west) / (east - west)) * 100}%`;
        marker.style.top = `${((north - cell.latitude) / (north - south)) * 100}%`;
        marker.style.backgroundColor = colorForCell(payload, index);
        marker.classList.toggle(
          "is-no-data",
          cell.variables.some(({ class_index: classIndex }) => classIndex === null),
        );
        marker.title = cell.region_id;
        return marker;
      }),
    );
  }
}
