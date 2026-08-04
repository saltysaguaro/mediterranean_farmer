import { describe, expect, it, vi } from "vitest";
import {
  DevelopmentTileLoader,
  PointSampleLoader,
  developmentTileUrl,
  pointSampleUrl,
} from "./data";
import { monthsToMask } from "./months";
import type { AppState, DevelopmentTile, LoadStatus, PointSample } from "./types";

const state: AppState = {
  xVariable: "spei_3",
  yVariable: "utci_daymax_median",
  year: 2024,
  monthMask: monthsToMask([1, 7]),
  view: { longitude: 12.5, latitude: 18, zoom: 1.1 },
};

const tile: DevelopmentTile = {
  status: "ok",
  format: "development_sparse_grid_cells",
  dataset_version: "sample-v1",
  year: 2024,
  month_mask: "041",
  months: [1, 7],
  fixture: true,
  official_evidence: false,
  scope: "deterministic interface test fixture; not climate observations",
  variables: [],
  cells: [],
};

const point: PointSample = {
  status: "no_data",
  dataset_version: "sample-v1",
  year: 2024,
  month_mask: "041",
  months: [1, 7],
  fixture: true,
  official_evidence: false,
  scope: "deterministic interface test fixture; not climate observations",
  requested_coordinate: { longitude: 10, latitude: 20 },
  reason: "outside_bounded_sample",
  variables: [],
};

describe("development map loading", () => {
  it("builds variable-neutral bivariate and univariate URLs", () => {
    expect(developmentTileUrl("/api", "sample-v1", state)).toBe(
      "/api/v1/tiles/sample-v1/spei_3/utci_daymax_median/2024/041/0/0/0",
    );
    expect(
      developmentTileUrl("/api", "sample-v1", { ...state, yVariable: null }),
    ).toContain("/spei_3/-/2024/");
    expect(pointSampleUrl("/api", state, -112.25, 34.25)).toBe(
      "/api/v1/sample?x=spei_3&y=utci_daymax_median&year=2024&months=041&lng=-112.25&lat=34.25",
    );
    expect(
      pointSampleUrl(
        "/api",
        { ...state, xVariable: "artificial_interface_fixture", yVariable: null },
        2,
        3,
      ),
    ).toContain("x=artificial_interface_fixture");
  });

  it("retains the last valid map when a replacement request fails", async () => {
    const statuses: LoadStatus[] = [];
    const maps: DevelopmentTile[] = [];
    let calls = 0;
    const fetchImplementation = vi.fn(async () => {
      calls += 1;
      if (calls === 1) {
        return new Response(JSON.stringify(tile), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(
        JSON.stringify({ error: { detail: "Selected months are unavailable." } }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      );
    }) as unknown as typeof fetch;
    const loader = new DevelopmentTileLoader(
      "/api",
      "sample-v1",
      {
        onStatus: (status) => statuses.push(status),
        onData: (payload) => maps.push(payload),
      },
      fetchImplementation,
    );

    loader.load(state);
    await vi.waitFor(() => expect(maps).toHaveLength(1));
    loader.load({ ...state, monthMask: monthsToMask([1]) });
    await vi.waitFor(() => expect(statuses.at(-1)?.kind).toBe("error"));

    expect(maps).toEqual([tile]);
    expect(statuses.at(-1)).toMatchObject({
      kind: "error",
      hasLastValidMap: true,
    });
    expect(statuses.at(-1)?.message).toContain("last valid map remains visible");
  });

  it("keeps a truthful no-data point response and marks it stale after failure", async () => {
    const statuses: LoadStatus[] = [];
    const points: PointSample[] = [];
    let calls = 0;
    const fetchImplementation = vi.fn(async () => {
      calls += 1;
      if (calls === 1) {
        return new Response(JSON.stringify(point), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ error: { detail: "Temporary failure." } }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      });
    }) as unknown as typeof fetch;
    const loader = new PointSampleLoader(
      "/api",
      {
        onStatus: (status) => statuses.push(status),
        onData: (payload) => points.push(payload),
      },
      fetchImplementation,
    );

    loader.load(state, 10, 20);
    await vi.waitFor(() => expect(points).toEqual([point]));
    loader.load(state, 11, 21);
    await vi.waitFor(() => expect(statuses.at(-1)?.kind).toBe("error"));

    expect(statuses.at(-1)).toMatchObject({ kind: "error", hasLastValidMap: true });
    expect(statuses.at(-1)?.message).toContain("previous readout remains visible and stale");
  });
});
