import { describe, expect, it } from "vitest";
import {
  APP_CONFIG,
  SCOPE_CONFIG,
  VARIABLES,
  compatibilityReason,
  publishedFallbackYears,
} from "./registry";

describe("manifest-driven registry", () => {
  it("loads the two public variables without hard-coded control copies", () => {
    expect(VARIABLES.map(({ id }) => id)).toEqual([
      "spei_3",
      "utci_daymax_median",
    ]);
    expect(APP_CONFIG.maximum_active_variables).toBe(2);
    expect(APP_CONFIG.service.api_base).toBe("/api");
    expect(SCOPE_CONFIG.name).toBe("Sicilia");
    expect(SCOPE_CONFIG.analysis_grid.included_cell_centers).toHaveLength(44);
    expect(VARIABLES.every(({ publication }) => publication.status === "published")).toBe(true);
    expect(VARIABLES.every(({ publication }) => publication.sample_retrieved_at !== null)).toBe(true);
    expect(publishedFallbackYears()).toEqual([2024, 2025]);
  });

  it("rejects duplicate axes and accepts the configured pair", () => {
    expect(compatibilityReason("spei_3", "spei_3", null)).toBe(
      "Choose two different variables.",
    );
    expect(
      compatibilityReason("spei_3", "utci_daymax_median", null),
    ).toBeNull();
  });
});
