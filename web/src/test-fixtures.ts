import type { VariableManifest } from "./types";

export function artificialCompatibleVariable(
  template: VariableManifest,
): VariableManifest {
  return {
    ...template,
    id: "artificial_interface_fixture",
    label: "Artificial interface variable — not climate observations",
    short_label: "Artificial fixture",
    description:
      "Deterministic interface-only values used to prove registry-driven behavior; these are not climate observations.",
    role_hint: "either",
    source: {
      ...template.source,
      dataset: "Deterministic interface fixture — not a provider dataset",
      provider: "Local structural test only",
      dataset_url: "https://example.invalid/not-climate-data",
      doi: "10.0000/not-a-climate-observation",
      product_version: "fixture-1",
      reference_period: null,
      license: "Test fixture only",
      license_url: "https://example.invalid/test-fixture-license",
    },
    aggregation: {
      ...template.aggregation,
      source_statistic: "deterministic monthly structural test values",
      temporal_note:
        "Deterministic monthly values exist only to exercise generic controls, medians, legends, and sampling code.",
    },
    quality: {
      policy: "none",
      mask: null,
      field: null,
      pass_values: [],
    },
    publication: {
      status: "sample",
      data_version: "deterministic-interface-fixture-v1",
      published_years: [2024],
      sample_retrieved_at: null,
    },
  };
}
