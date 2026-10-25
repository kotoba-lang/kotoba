import type { Embedding768Row, EmbeddingSourceRow } from "./embedding-768.js";

export interface SqlStatement {
  text: string;
  values: readonly unknown[];
}

const SOURCE_COLUMNS = [
  "vertex_id",
  "source_uri",
  "source_cid",
  "source_kind",
  "source_table",
  "source_vertex_id",
  "source_collection",
  "repo",
  "rkey",
  "tenant_id",
  "shard_id",
  "modality",
  "media_type",
  "lang",
  "text_preview",
  "content_hash",
  "blob_ref",
  "width_px",
  "height_px",
  "duration_ms",
  "sample_rate_hz",
  "frame_rate_millis",
  "sensor_vendor",
  "sensor_model",
  "sensor_frame",
  "captured_at",
  "indexed_at",
  "visibility",
  "safety_label",
  "metadata_json",
  "created_at",
] as const;

const EMBEDDING_COLUMNS = [
  "embedding_id",
  "source_uri",
  "chunk_id",
  "source_vertex_id",
  "tenant_id",
  "shard_id",
  "modality",
  "model_id",
  "space_id",
  "model_version",
  "projection_id",
  "emb",
  "text_preview",
  "created_at",
  "embedded_at",
] as const;

export function insertSourceSql(row: EmbeddingSourceRow): SqlStatement {
  return insertSql("vertex_vector_embedding_source", SOURCE_COLUMNS, row);
}

export function insertEmbedding768Sql(row: Embedding768Row): SqlStatement {
  return insertSql("vertex_vector_embedding_768", EMBEDDING_COLUMNS, row, {
    emb: "vector(768)",
  });
}

function insertSql(
  table: string,
  columns: readonly string[],
  row: Record<string, unknown>,
  casts: Record<string, string> = {},
): SqlStatement {
  const columnSql = columns.join(", ");
  const placeholders = columns
    .map((column, index) => {
      const placeholder = `$${index + 1}`;
      const cast = casts[column];
      return cast ? `${placeholder}::${cast}` : placeholder;
    })
    .join(", ");
  return {
    text: `INSERT INTO ${table} (${columnSql}) VALUES (${placeholders})`,
    values: columns.map((column) => row[column] ?? null),
  };
}
