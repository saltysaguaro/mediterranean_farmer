import { describe, expect, it } from "vitest";
import { monthsToMask } from "./months";
import { parseUrlState, stateUrl, type StateConstraints } from "./state";
import type { AppState } from "./types";

const fallback: AppState = {
  xVariable: "spei_3",
  yVariable: "utci_daymax_median",
  year: 2024,
  monthMask: monthsToMask([1, 7]),
  view: { longitude: 12.5, latitude: 18, zoom: 1.1 },
};

const constraints: StateConstraints = {
  variableIds: ["spei_3", "utci_daymax_median", "fixture_variable"],
  years: [2024, 2025],
  monthsByYear: new Map([
    [2024, [1, 7]],
    [2025, Array.from({ length: 12 }, (_, index) => index + 1)],
  ]),
  maximumZoom: 6,
};

describe("URL state", () => {
  it("round-trips variables, year, arbitrary months, location, and zoom", () => {
    const expected: AppState = {
      xVariable: "fixture_variable",
      yVariable: "spei_3",
      year: 2025,
      monthMask: monthsToMask([1, 4, 9]),
      view: { longitude: -112.25, latitude: 34.25, zoom: 3.5 },
    };
    const url = stateUrl(expected, new URL("https://example.test/map?ignored=kept"));
    const parsed = parseUrlState(url, fallback, constraints);

    expect(url.searchParams.get("ignored")).toBe("kept");
    expect(parsed).toEqual({ state: expected, warnings: [] });
  });

  it("restores safe defaults for invalid or unpublished values", () => {
    const url = new URL(
      "https://example.test/?x=unknown&y=spei_3&year=2024&months=fff&lng=999&lat=0&zoom=2",
    );
    const parsed = parseUrlState(url, fallback, constraints);

    expect(parsed.state).toEqual(fallback);
    expect(parsed.warnings).toHaveLength(4);
  });

  it("serializes univariate mode explicitly", () => {
    const url = stateUrl(
      { ...fallback, yVariable: null },
      new URL("https://example.test/map"),
    );

    expect(url.searchParams.get("y")).toBe("-");
    expect(parseUrlState(url, fallback, constraints).state.yVariable).toBeNull();
  });

  it("never restores duplicate axes when only X changes", () => {
    const parsed = parseUrlState(
      new URL("https://example.test/?x=utci_daymax_median"),
      fallback,
      constraints,
    );

    expect(parsed.state.xVariable).toBe("utci_daymax_median");
    expect(parsed.state.yVariable).toBeNull();
  });
});
