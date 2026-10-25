import { toUnitVector768, VECTOR_DIMENSION } from "./embedding-768.js";
import type { EmbeddingModelSpec } from "./model-catalog.js";

export interface ProjectionResult {
  vector768: number[];
  projectionId: string;
}

export function projectTo768(
  vector: readonly number[],
  model: EmbeddingModelSpec,
): ProjectionResult {
  if (vector.length !== model.nativeDimension) {
    throw new Error(
      `${model.modelId} expected ${model.nativeDimension} dimensions, got ${vector.length}`,
    );
  }

  const projected = projectByPhase1Rule(vector);
  return {
    vector768: toUnitVector768(projected),
    projectionId: model.projectionId,
  };
}

function projectByPhase1Rule(vector: readonly number[]): number[] {
  if (vector.length === VECTOR_DIMENSION) return [...vector];
  if (vector.length > VECTOR_DIMENSION) return vector.slice(0, VECTOR_DIMENSION);

  const padded = [...vector];
  while (padded.length < VECTOR_DIMENSION) padded.push(0);
  return padded;
}
