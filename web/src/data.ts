import { maskToHex } from "./months";
import type {
  AppState,
  Availability,
  LosslessMapResponse,
  LoadStatus,
  PointSample,
} from "./types";

export type FetchImplementation = typeof fetch;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const payload: unknown = await response.json();
    if (isRecord(payload) && isRecord(payload.error) && typeof payload.error.detail === "string") {
      return payload.error.detail;
    }
  } catch {
    // The stable status message below remains safe for non-JSON failures.
  }
  return `The data service returned HTTP ${response.status}.`;
}

function assertAvailability(payload: unknown): asserts payload is Availability {
  if (
    !isRecord(payload) ||
    payload.status !== "ok" ||
    !Array.isArray(payload.years) ||
    !Array.isArray(payload.variables) ||
    !Array.isArray(payload.compatibility) ||
    typeof payload.dataset_version !== "string" ||
    typeof payload.scope !== "string"
  ) {
    throw new Error("The data service returned an invalid availability response.");
  }
}

function assertLosslessMapResponse(payload: unknown): asserts payload is LosslessMapResponse {
  if (
    !isRecord(payload) ||
    (payload.status !== "ok" && payload.status !== "no_data") ||
    payload.format !== "lossless_sparse_grid_cells_v1" ||
    !Array.isArray(payload.cells) ||
    typeof payload.scope !== "string"
  ) {
    throw new Error("The data service returned an invalid lossless map response.");
  }
}

function assertPointSample(payload: unknown): asserts payload is PointSample {
  if (
    !isRecord(payload) ||
    !["ok", "partial_data", "no_data"].includes(String(payload.status)) ||
    !isRecord(payload.requested_coordinate) ||
    !Array.isArray(payload.variables) ||
    typeof payload.scope !== "string"
  ) {
    throw new Error("The data service returned an invalid point response.");
  }
}

export async function fetchAvailability(
  apiBase: string,
  signal?: AbortSignal,
  fetchImplementation: FetchImplementation = globalThis.fetch.bind(globalThis),
): Promise<Availability> {
  const response = await fetchImplementation(`${apiBase.replace(/\/$/, "")}/v1/availability`, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(await errorDetail(response));
  }
  const payload: unknown = await response.json();
  assertAvailability(payload);
  return payload;
}

export function mapResponseUrl(
  apiBase: string,
  datasetVersion: string,
  state: AppState,
): string {
  const yVariable = state.yVariable ?? "-";
  const parts = [
    apiBase.replace(/\/$/, ""),
    "v1",
    "tiles",
    datasetVersion,
    state.xVariable,
    yVariable,
    String(state.year),
    maskToHex(state.monthMask),
    "0",
    "0",
    "0",
  ];
  return parts.map((part, index) => (index === 0 ? part : encodeURIComponent(part))).join("/");
}

export function pointSampleUrl(
  apiBase: string,
  state: AppState,
  longitude: number,
  latitude: number,
): string {
  const url = new URL(
    `${apiBase.replace(/\/$/, "")}/v1/sample`,
    "https://local.invalid",
  );
  url.searchParams.set("x", state.xVariable);
  if (state.yVariable) {
    url.searchParams.set("y", state.yVariable);
  }
  url.searchParams.set("year", String(state.year));
  url.searchParams.set("months", maskToHex(state.monthMask));
  url.searchParams.set("lng", String(longitude));
  url.searchParams.set("lat", String(latitude));
  return `${url.pathname}${url.search}`;
}

export interface MapLoaderCallbacks {
  onStatus(status: LoadStatus): void;
  onData(payload: LosslessMapResponse): void;
}

export class MapResponseLoader {
  private active: AbortController | null = null;
  private sequence = 0;
  private hasLastValidMap = false;

  constructor(
    private readonly apiBase: string,
    private readonly datasetVersion: string,
    private readonly callbacks: MapLoaderCallbacks,
    private readonly fetchImplementation: FetchImplementation = globalThis.fetch.bind(globalThis),
  ) {}

  load(state: AppState): void {
    this.active?.abort();
    const controller = new AbortController();
    this.active = controller;
    const sequence = ++this.sequence;
    this.callbacks.onStatus({
      kind: "updating",
      hasLastValidMap: this.hasLastValidMap,
      message: this.hasLastValidMap
        ? "Updating the bounded sample; the last valid map remains visible."
        : "Loading the bounded official sample.",
    });

    void this.fetchTile(state, controller, sequence);
  }

  retry(state: AppState): void {
    this.load(state);
  }

  dispose(): void {
    this.active?.abort();
  }

  private async fetchTile(
    state: AppState,
    controller: AbortController,
    sequence: number,
  ): Promise<void> {
    try {
      const request = this.fetchImplementation;
      const response = await request(
        mapResponseUrl(this.apiBase, this.datasetVersion, state),
        {
          signal: controller.signal,
          headers: { Accept: "application/json" },
        },
      );
      if (!response.ok) {
        throw new Error(await errorDetail(response));
      }
      const payload: unknown = await response.json();
      assertLosslessMapResponse(payload);
      if (sequence !== this.sequence) {
        return;
      }
      this.hasLastValidMap = true;
      this.callbacks.onData(payload);
      this.callbacks.onStatus({
        kind: "ready",
        hasLastValidMap: true,
        message:
          payload.status === "no_data"
            ? "No published sample cells intersect this view."
            : "Official Sicily data are ready.",
      });
    } catch (error) {
      if (controller.signal.aborted || sequence !== this.sequence) {
        return;
      }
      const message = error instanceof Error ? error.message : "The map request failed.";
      this.callbacks.onStatus({
        kind: "error",
        hasLastValidMap: this.hasLastValidMap,
        message: this.hasLastValidMap
          ? `${message} The last valid map remains visible.`
          : message,
      });
    }
  }
}

export interface PointLoaderCallbacks {
  onStatus(status: LoadStatus): void;
  onData(payload: PointSample): void;
}

export class PointSampleLoader {
  private active: AbortController | null = null;
  private sequence = 0;
  private hasLastValidSample = false;

  constructor(
    private readonly apiBase: string,
    private readonly callbacks: PointLoaderCallbacks,
    private readonly fetchImplementation: FetchImplementation = globalThis.fetch.bind(globalThis),
  ) {}

  load(state: AppState, longitude: number, latitude: number): void {
    this.active?.abort();
    const controller = new AbortController();
    this.active = controller;
    const sequence = ++this.sequence;
    this.callbacks.onStatus({
      kind: "updating",
      hasLastValidMap: this.hasLastValidSample,
      message: this.hasLastValidSample
        ? "Updating this grid-cell readout; the previous values are marked stale."
        : "Loading the selected grid-cell readout.",
    });
    void this.fetchSample(state, longitude, latitude, controller, sequence);
  }

  dispose(): void {
    this.active?.abort();
  }

  private async fetchSample(
    state: AppState,
    longitude: number,
    latitude: number,
    controller: AbortController,
    sequence: number,
  ): Promise<void> {
    try {
      const response = await this.fetchImplementation(
        pointSampleUrl(this.apiBase, state, longitude, latitude),
        {
          signal: controller.signal,
          headers: { Accept: "application/json" },
        },
      );
      if (!response.ok) {
        throw new Error(await errorDetail(response));
      }
      const payload: unknown = await response.json();
      assertPointSample(payload);
      if (sequence !== this.sequence) {
        return;
      }
      this.hasLastValidSample = true;
      this.callbacks.onData(payload);
      this.callbacks.onStatus({
        kind: "ready",
        hasLastValidMap: true,
        message:
          payload.status === "no_data"
            ? "No published value exists at this coordinate for the selected period."
            : payload.status === "partial_data"
              ? "Some selected variables are no data; available values remain visible."
              : "Grid-cell readout is ready.",
      });
    } catch (error) {
      if (controller.signal.aborted || sequence !== this.sequence) {
        return;
      }
      const message = error instanceof Error ? error.message : "The point request failed.";
      this.callbacks.onStatus({
        kind: "error",
        hasLastValidMap: this.hasLastValidSample,
        message: this.hasLastValidSample
          ? `${message} The previous readout remains visible and stale.`
          : message,
      });
    }
  }
}
