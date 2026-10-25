import { etzhayyim_MM_768_SPACE_ID, vectorLiteral, type Modality } from "./embedding-768.js";
import type { SqlStatement } from "./sql.js";

export interface VectorSearchQuery {
  vector: readonly number[];
  limit?: number;
  tenantId?: string;
  shardId?: number;
  modality?: Modality;
  modelId?: string;
  spaceId?: string;
  createdAfter?: string;
}

export function searchEmbedding768Sql(query: VectorSearchQuery): SqlStatement {
  const values: unknown[] = [vectorLiteral(query.vector)];
  const where: string[] = [`space_id = $2`];
  values.push(query.spaceId ?? etzhayyim_MM_768_SPACE_ID);

  if (query.tenantId) {
    values.push(query.tenantId);
    where.push(`tenant_id = $${values.length}`);
  }
  if (query.shardId !== undefined) {
    values.push(query.shardId);
    where.push(`shard_id = $${values.length}`);
  }
  if (query.modality) {
    values.push(query.modality);
    where.push(`modality = $${values.length}`);
  }
  if (query.modelId) {
    values.push(query.modelId);
    where.push(`model_id = $${values.length}`);
  }
  if (query.createdAfter) {
    values.push(query.createdAfter);
    where.push(`created_at >= $${values.length}`);
  }

  const limit = Math.max(1, Math.min(Math.floor(query.limit ?? 50), 500));
  values.push(limit);

  return {
    text: `
SELECT
  embedding_id,
  source_uri,
  chunk_id,
  source_vertex_id,
  tenant_id,
  shard_id,
  modality,
  model_id,
  space_id,
  model_version,
  projection_id,
  text_preview,
  created_at,
  emb <=> $1::vector(768) AS distance
FROM vertex_vector_embedding_768
WHERE ${where.join("\n  AND ")}
ORDER BY emb <=> $1::vector(768)
LIMIT $${values.length}
`.trim(),
    values,
  };
}
