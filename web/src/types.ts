export interface ClassificationManifest {
  breaks: number[];
  break_assignments: ("lower_class" | "upper_class")[];
  labels: string[];
  axis_display_order: "ascending" | "descending";
  version: string;
}

export interface VariableManifest {
  id: string;
  label: string;
  short_label: string;
  description: string;
  unit: string;
  role_hint: "x" | "y" | "either";
  grid_id: string;
  source: {
    dataset: string;
    provider: string;
    dataset_url: string;
    doi: string;
    product_version: string;
    reference_period: string | null;
    license: string;
    license_url: string;
  };
  coverage: {
    bbox: [number, number, number, number];
    resolution_degrees: number;
    months: number[];
  };
  aggregation: {
    default: string;
    minimum_valid_fraction: number;
    source_statistic: string;
    temporal_note: string;
  };
  classification: ClassificationManifest;
  quality: {
    policy: "none" | "mask" | "flag";
    mask: string | null;
    field: string | null;
    pass_values: number[];
  };
  publication: {
    status: string;
    data_version: string;
    published_years: number[];
    sample_retrieved_at: string | null;
  };
}

export interface AppConfiguration {
  title: string;
  scope: string;
  maximum_active_variables: number;
  default_view: {
    x_variable: string;
    y_variable: string;
    month_mask: string;
    year_policy: string;
  };
  service: {
    api_version: string;
    dataset_version: string;
    api_base: string;
    maximum_zoom: number;
  };
}

export interface ScopeConfiguration {
  scope_id: string;
  name: string;
  country: string;
  analysis_grid: {
    grid_id: string;
    resolution_degrees: number;
    acquisition_bbox: [number, number, number, number];
    included_cell_centers: [number, number][];
  };
  map: {
    bounds: [number, number, number, number];
    initial_center: [number, number];
    initial_zoom: number;
    minimum_zoom: number;
    maximum_zoom: number;
  };
  boundary_source: {
    authority: string;
    dataset: string;
    dataset_url: string;
    license: string;
    license_url: string;
    retrieved_at: string;
  };
  limitations: string[];
}

export interface AvailabilityYear {
  year: number;
  months: number[];
  complete: boolean;
  regions: string[];
}

export interface AvailabilityVariable {
  id: string;
  label: string;
  unit: string;
  data_version: string;
  published_years: number[];
  sample_retrieved_at?: string | null;
}

export interface CompatibilityRecord {
  variables: [string, string];
  compatible: boolean;
  reason: string | null;
}

export interface Availability {
  status: "ok";
  dataset_version: string;
  fixture: boolean;
  official_evidence: boolean;
  scope: string;
  maximum_active_variables: number;
  latest_complete_year: number | null;
  years: AvailabilityYear[];
  variables: AvailabilityVariable[];
  compatibility: CompatibilityRecord[];
}

export interface MapView {
  longitude: number;
  latitude: number;
  zoom: number;
}

export interface AppState {
  xVariable: string;
  yVariable: string | null;
  year: number;
  monthMask: number;
  view: MapView;
}

export interface TileVariableRecord {
  id: string;
  label: string;
  unit: string;
  value: number | null;
  class_index: number | null;
  class_label: string | null;
  status: string;
  quality_state: string;
  valid_month_count: number;
  required_valid_month_count: number | null;
  selected_month_count: number | null;
  quality_pass_month_count: number | null;
  source: PointSource;
}

export interface TileCell {
  region_id: string;
  latitude: number;
  longitude: number;
  variables: TileVariableRecord[];
}

export interface LosslessMapResponse {
  status: "ok" | "no_data";
  format: "lossless_sparse_grid_cells_v1";
  dataset_version: string;
  year: number;
  month_mask: string;
  months: number[];
  fixture: boolean;
  official_evidence: boolean;
  scope: string;
  variables: AvailabilityVariable[];
  cells: TileCell[];
}

export interface PointSource {
  dataset: string;
  provider?: string;
  product_version: string;
  reference_period?: string | null;
  doi?: string;
  sample_retrieved_at: string | null;
}

export interface PointVariableRecord extends TileVariableRecord {}

export interface PointSample {
  status: "ok" | "partial_data" | "no_data";
  dataset_version: string;
  year: number;
  month_mask: string;
  months: number[];
  fixture: boolean;
  official_evidence: boolean;
  scope: string;
  requested_coordinate: {
    latitude: number;
    longitude: number;
  };
  reason?: string;
  region_id?: string;
  grid_cell?: {
    latitude: number;
    longitude: number;
    row: number;
    column: number;
  };
  quality_warning?: boolean;
  variables: PointVariableRecord[];
}

export type LoadStatus =
  | { kind: "idle"; hasLastValidMap: boolean; message: string }
  | { kind: "updating"; hasLastValidMap: boolean; message: string }
  | { kind: "ready"; hasLastValidMap: true; message: string }
  | { kind: "error"; hasLastValidMap: boolean; message: string };
