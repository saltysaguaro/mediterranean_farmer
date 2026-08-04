import { hexToMask, maskToHex, monthsToMask } from "./months";
import type { AppState, Availability, MapView } from "./types";

export interface StateConstraints {
  variableIds: readonly string[];
  years: readonly number[];
  monthsByYear: ReadonlyMap<number, readonly number[]>;
  maximumZoom: number;
}

export interface ParsedState {
  state: AppState;
  warnings: string[];
}

function finiteNumber(value: string | null, fallback: number, name: string, warnings: string[]) {
  if (value === null || value.trim() === "") {
    return fallback;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    warnings.push(`Invalid ${name}; restored the previous value.`);
    return fallback;
  }
  return parsed;
}

function validView(
  candidate: MapView,
  fallback: MapView,
  maximumZoom: number,
  warnings: string[],
): MapView {
  if (
    candidate.longitude < -180 ||
    candidate.longitude >= 180 ||
    candidate.latitude < -85 ||
    candidate.latitude > 85 ||
    candidate.zoom < 0 ||
    candidate.zoom > maximumZoom
  ) {
    warnings.push("Invalid map location or zoom; restored the previous view.");
    return fallback;
  }
  return candidate;
}

export function constraintsFromAvailability(
  availability: Availability,
  maximumZoom: number,
): StateConstraints {
  return {
    variableIds: availability.variables.map(({ id }) => id),
    years: availability.years.map(({ year }) => year),
    monthsByYear: new Map(
      availability.years.map(({ year, months }) => [year, months] as const),
    ),
    maximumZoom,
  };
}

export function parseUrlState(
  url: URL,
  fallback: AppState,
  constraints: StateConstraints,
): ParsedState {
  const warnings: string[] = [];
  const xCandidate = url.searchParams.get("x");
  const xVariable =
    xCandidate && constraints.variableIds.includes(xCandidate)
      ? xCandidate
      : fallback.xVariable;
  if (xCandidate && xCandidate !== xVariable) {
    warnings.push("Unknown X-axis variable; restored the default.");
  }

  const yCandidate = url.searchParams.get("y");
  let yVariable = fallback.yVariable;
  if (yCandidate === "-") {
    yVariable = null;
  } else if (yCandidate !== null) {
    if (constraints.variableIds.includes(yCandidate) && yCandidate !== xVariable) {
      yVariable = yCandidate;
    } else {
      warnings.push("Invalid Y-axis variable; restored the default.");
    }
  }
  if (yVariable === xVariable) {
    yVariable = null;
    if (yCandidate === null) {
      warnings.push("Duplicate axes are not allowed; restored univariate mode.");
    }
  }

  const yearCandidate = Number(url.searchParams.get("year"));
  const year =
    Number.isInteger(yearCandidate) && constraints.years.includes(yearCandidate)
      ? yearCandidate
      : fallback.year;
  if (url.searchParams.has("year") && yearCandidate !== year) {
    warnings.push("Unavailable year; restored the latest available year.");
  }

  let monthMask = fallback.monthMask;
  const monthCandidate = url.searchParams.get("months");
  if (monthCandidate !== null) {
    try {
      const parsed = hexToMask(monthCandidate);
      const availableMask = monthsToMask(constraints.monthsByYear.get(year) ?? []);
      if ((parsed & ~availableMask) !== 0) {
        throw new Error("Selected months are not published for this year.");
      }
      monthMask = parsed;
    } catch {
      warnings.push("Unavailable month selection; restored the available period.");
    }
  }

  const view = validView(
    {
      longitude: finiteNumber(
        url.searchParams.get("lng"),
        fallback.view.longitude,
        "longitude",
        warnings,
      ),
      latitude: finiteNumber(
        url.searchParams.get("lat"),
        fallback.view.latitude,
        "latitude",
        warnings,
      ),
      zoom: finiteNumber(url.searchParams.get("zoom"), fallback.view.zoom, "zoom", warnings),
    },
    fallback.view,
    constraints.maximumZoom,
    warnings,
  );

  return {
    state: { xVariable, yVariable, year, monthMask, view },
    warnings,
  };
}

function conciseNumber(value: number): string {
  return Number(value.toFixed(4)).toString();
}

export function stateUrl(state: AppState, current: URL): URL {
  const url = new URL(current);
  url.searchParams.set("x", state.xVariable);
  url.searchParams.set("y", state.yVariable ?? "-");
  url.searchParams.set("year", String(state.year));
  url.searchParams.set("months", maskToHex(state.monthMask));
  url.searchParams.set("lng", conciseNumber(state.view.longitude));
  url.searchParams.set("lat", conciseNumber(state.view.latitude));
  url.searchParams.set("zoom", conciseNumber(state.view.zoom));
  return url;
}

export function sameState(left: AppState, right: AppState): boolean {
  return (
    left.xVariable === right.xVariable &&
    left.yVariable === right.yVariable &&
    left.year === right.year &&
    left.monthMask === right.monthMask &&
    left.view.longitude === right.view.longitude &&
    left.view.latitude === right.view.latitude &&
    left.view.zoom === right.view.zoom
  );
}
