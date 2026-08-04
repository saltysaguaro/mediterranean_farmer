import appJson from "../../config/app.json";
import speiJson from "../../config/variables/spei_3.json";
import utciJson from "../../config/variables/utci_daymax_median.json";
import type { AppConfiguration, VariableManifest } from "./types";

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
    !candidate.service ||
    typeof candidate.service.development_api_base !== "string"
  ) {
    throw new Error("The bundled application configuration is incomplete.");
  }
  return candidate as AppConfiguration;
}

export const APP_CONFIG = asConfiguration(appJson);
const REGISTRY = createVariableRegistry([speiJson, utciJson]);
export const VARIABLES = REGISTRY.variables;
export const VARIABLE_BY_ID = REGISTRY.byId;

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
