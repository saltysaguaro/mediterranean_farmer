import { describe, expect, it } from "vitest";
import { APP_CONFIG, VARIABLES, compatibilityReason } from "./registry";

describe("manifest-driven registry", () => {
  it("loads the two public variables without hard-coded control copies", () => {
    expect(VARIABLES.map(({ id }) => id)).toEqual([
      "spei_3",
      "utci_daymax_median",
    ]);
    expect(APP_CONFIG.maximum_active_variables).toBe(2);
    expect(APP_CONFIG.service.development_api_base).toBe("/api");
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
