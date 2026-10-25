import {
  stableEmbeddingId,
  toEmbedding768Row,
  toEmbeddingSourceRow,
  type Embedding768Row,
  type EmbeddingSourceInput,
  type EmbeddingSourceRow,
  type Modality,
} from "./embedding-768.js";
import { assertModelSupportsModality, modelForModality, type EmbeddingModelSpec } from "./model-catalog.js";
import { projectTo768 } from "./projection.js";

export interface VectorEmbeddingJob {
  source: EmbeddingSourceInput;
  nativeVector: readonly number[];
  model?: EmbeddingModelSpec;
  modelVersion?: string;
  chunkId?: string;
  textPreview?: string;
}

export interface VectorEmbeddingPlan {
  sourceRow: EmbeddingSourceRow;
  embeddingRow: Embedding768Row;
  model: EmbeddingModelSpec;
}

export function planVectorEmbeddingJob(job: VectorEmbeddingJob): VectorEmbeddingPlan {
  const modality = job.source.modality satisfies Modality;
  const model = job.model ?? modelForModality(modality);
  assertModelSupportsModality(model, modality);

  const projected = projectTo768(job.nativeVector, model);
  const base = {
    sourceUri: job.source.sourceUri,
    chunkId: job.chunkId,
    sourceVertexId: job.source.sourceVertexId,
    tenantId: job.source.tenantId,
    shardId: job.source.shardId,
    modality,
    modelId: model.modelId,
    modelVersion: job.modelVersion ?? "initial",
    projectionId: projected.projectionId,
    textPreview: job.textPreview ?? job.source.textPreview,
  };

  return {
    sourceRow: toEmbeddingSourceRow(job.source),
    embeddingRow: toEmbedding768Row({
      ...base,
      embeddingId: stableEmbeddingId(base),
      vector: projected.vector768,
    }),
    model,
  };
}
