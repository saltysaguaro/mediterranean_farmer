import { describe, expect, it } from "vitest";
import { pointClassPair, qualityLabel } from "./inspection";
import type { PointSample, PointVariableRecord } from "./types";

function variable(overrides: Partial<PointVariableRecord> = {}): PointVariableRecord {
  return {
    id: "deterministic_fixture",
    label: "Deterministic test fixture — not climate observations",
    unit: "fixture units",
    value: 0,
    class_index: 1,
    class_label: "Middle fixture class",
    status: "ok",
    quality_state: "passes",
    valid_month_count: 2,
    required_valid_month_count: 2,
    selected_month_count: 2,
    quality_pass_month_count: 2,
    source: {
      dataset: "Deterministic fixture",
      product_version: "fixture-1",
      sample_retrieved_at: null,
    },
    ...overrides,
  };
}

function sample(variables: PointVariableRecord[]): PointSample {
  return {
    status: "ok",
    dataset_version: "fixture-v1",
    year: 2024,
    month_mask: "041",
    months: [1, 7],
    fixture: true,
    official_evidence: false,
    scope: "deterministic test fixture; not climate observations",
    requested_coordinate: { latitude: 0, longitude: 0 },
    variables,
  };
}

describe("point interpretation", () => {
  it("links complete bivariate classes to one legend cell", () => {
    expect(pointClassPair(sample([variable({ class_index: 2 }), variable({ class_index: 0 })]))).toEqual({
      xClass: 2,
      yClass: 0,
    });
    expect(pointClassPair(sample([variable({ class_index: null, value: null })]))).toBeNull();
  });

  it("describes provider quality without converting missing values to zero", () => {
    const lowQuality = variable({
      value: null,
      class_index: null,
      class_label: "No data",
      status: "no_data",
      quality_state: "low_quality",
      valid_month_count: 0,
      quality_pass_month_count: 0,
    });

    expect(qualityLabel(lowQuality)).toContain("remains no data");
    expect(lowQuality.value).toBeNull();
  });
});
