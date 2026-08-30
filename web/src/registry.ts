import appJson from "../../config/app.json";
import scopeJson from "../../config/scope.json";
import speiJson from "../../config/variables/spei_3.json";
import utciJson from "../../config/variables/utci_daymax_median.json";
import type { AppConfiguration, ScopeConfiguration, VariableManifest } from "./types";

export function asVariableManifest(value: unknown): VariableManifest {
  const candidate = value as Partial<VariableManifest>;
  if (
    typeof candidate.id !== "string" ||
    typeof candidate.label !== "string" ||
    typeof candidate.short_label !== "string" ||
    !candidate.classification ||
    !Array.isArray(candidate.classification.labels) ||
    !candidate.publication
  ) {
    throw new Error("The bundled variable manifest is incomplete.");
  }
  return candidate as VariableManifest;
}

export interface VariableRegistry {
  variables: VariableManifest[];
  byId: Map<string, VariableManifest>;
}

export function createVariableRegistry(values: unknown[]): VariableRegistry {
  const variables = values.map(asVariableManifest);
  const byId = new Map(variables.map((variable) => [variable.id, variable]));
  if (byId.size !== variables.length) {
    throw new Error("Bundled variable IDs must be unique.");
  }
  return { variables, byId };
}

function asConfiguration(value: unknown): AppConfiguration {
  const candidate = value as Partial<AppConfiguration>;
  if (
    candidate.maximum_active_variables !== 2 ||
    !candidate.default_view ||
    typeof candidate.scope !== "string" ||
    !candidate.service ||
    typeof candidate.service.api_base !== "string"
  ) {
    throw new Error("The bundled application configuration is incomplete.");
  }
  return candidate as AppConfiguration;
}

function asScopeConfiguration(value: unknown): ScopeConfiguration {
  const candidate = value as Partial<ScopeConfiguration>;
  if (
    candidate.scope_id !== "sicily_istat_2026_grid_centers" ||
    candidate.name !== "Sicilia" ||
    !candidate.analysis_grid ||
    candidate.analysis_grid.grid_id !== "era5_latlon_0_25" ||
    candidate.analysis_grid.included_cell_centers.length !== 44 ||
    !candidate.map ||
    candidate.map.bounds.length !== 4
  ) {
    throw new Error("The bundled Sicily scope configuration is incomplete.");
  }
  return candidate as ScopeConfiguration;
}

export const APP_CONFIG = asConfiguration(appJson);
export const SCOPE_CONFIG = asScopeConfiguration(scopeJson);
const REGISTRY = createVariableRegistry([speiJson, utciJson]);
export const VARIABLES = REGISTRY.variables;
export const VARIABLE_BY_ID = REGISTRY.byId;

export function publishedFallbackYears(): number[] {
  return Array.from(
    new Set(
      VARIABLES.filter(({ publication }) => publication.status !== "planned").flatMap(
        ({ publication }) => publication.published_years,
      ),
    ),
  ).sort();
}

export function variableById(id: string): VariableManifest {
  const variable = VARIABLE_BY_ID.get(id);
  if (!variable) {
    throw new Error(`Unknown variable: ${id}`);
  }
  return variable;
}

export function compatibilityReason(
  leftId: string,
  rightId: string,
  unavailableReason: string | null,
): string | null {
  const left = variableById(leftId);
  const right = variableById(rightId);
  if (left.id === right.id) {
    return "Choose two different variables.";
  }
  if (unavailableReason) {
    return unavailableReason;
  }
  if (left.grid_id !== right.grid_id) {
    return "The variables do not share a grid.";
  }
  if (left.aggregation.default !== right.aggregation.default) {
    return "The variables do not share an aggregation statistic.";
  }
  return null;
}
