export const etzhayyim_MM_768_SPACE_ID = "etzhayyim-mm-768";
export const VECTOR_DIMENSION = 768;

export type Modality =
  | "text"
  | "image"
  | "video"
  | "audio"
  | "screenshot"
  | "pdf"
  | "depth"
  | "thermal"
  | "imu"
  | "sensor"
  | "mixed";

export interface EmbeddingSourceInput {
  sourceUri: string;
  sourceCid?: string;
  sourceKind: string;
  sourceTable?: string;
  sourceVertexId?: string;
  sourceCollection?: string;
  repo?: string;
  rkey?: string;
  tenantId?: string;
  shardId?: number;
  modality: Modality;
  mediaType?: string;
  lang?: string;
  textPreview?: string;
  contentHash?: string;
  blobRef?: string;
  widthPx?: number;
  heightPx?: number;
  durationMs?: number;
  sampleRateHz?: number;
  frameRateMillis?: number;
  sensorVendor?: string;
  sensorModel?: string;
  sensorFrame?: string;
  capturedAt?: string;
  indexedAt?: string;
  visibility?: string;
  safetyLabel?: string;
  metadataJson?: string;
}

export interface Embedding768Input {
  embeddingId: string;
  sourceUri: string;
  chunkId?: string;
  sourceVertexId?: string;
  tenantId?: string;
  shardId?: number;
  modality: Modality;
  modelId: string;
  modelVersion?: string;
  projectionId: string;
  vector: readonly number[];
  textPreview?: string;
  createdAt?: string;
  embeddedAt?: string;
}

export type EmbeddingSourceRow = Record<string, string | number | null>;
export type Embedding768Row = Record<string, string | number | null>;

export function toUnitVector768(vector: readonly number[]): number[] {
  if (vector.length !== VECTOR_DIMENSION) {
    throw new Error(`expected ${VECTOR_DIMENSION} dimensions, got ${vector.length}`);
  }

  let sumSquares = 0;
  for (const value of vector) {
    if (!Number.isFinite(value)) {
      throw new Error("embedding vector contains a non-finite value");
    }
    sumSquares += value * value;
  }

  const norm = Math.sqrt(sumSquares);
  if (norm === 0) {
    throw new Error("embedding vector norm is zero");
  }

  return vector.map((value) => value / norm);
}

export function vectorLiteral(vector: readonly number[]): string {
  const unit = toUnitVector768(vector);
  return `[${unit.map((value) => Number(value).toPrecision(8)).join(",")}]`;
}

export function stableEmbeddingId(input: Omit<Embedding768Input, "embeddingId" | "vector">): string {
  const chunk = input.chunkId ?? "root";
  const version = input.modelVersion ?? "initial";
  return [
    "emb768",
    etzhayyim_MM_768_SPACE_ID,
    input.modelId,
    input.projectionId,
    input.sourceUri,
    chunk,
    version,
  ].join(":");
}

export function toEmbeddingSourceRow(input: EmbeddingSourceInput): EmbeddingSourceRow {
  const now = new Date().toISOString();
  const vertexId = `embedding-source:${input.sourceUri}`;

  return {
    vertex_id: vertexId,
    source_uri: input.sourceUri,
    source_cid: input.sourceCid ?? null,
    source_kind: input.sourceKind,
    source_table: input.sourceTable ?? null,
    source_vertex_id: input.sourceVertexId ?? null,
    source_collection: input.sourceCollection ?? null,
    repo: input.repo ?? null,
    rkey: input.rkey ?? null,
    tenant_id: input.tenantId ?? "public",
    shard_id: input.shardId ?? null,
    modality: input.modality,
    media_type: input.mediaType ?? null,
    lang: input.lang ?? null,
    text_preview: input.textPreview ?? null,
    content_hash: input.contentHash ?? null,
    blob_ref: input.blobRef ?? null,
    width_px: input.widthPx ?? null,
    height_px: input.heightPx ?? null,
    duration_ms: input.durationMs ?? null,
    sample_rate_hz: input.sampleRateHz ?? null,
    frame_rate_millis: input.frameRateMillis ?? null,
    sensor_vendor: input.sensorVendor ?? null,
    sensor_model: input.sensorModel ?? null,
    sensor_frame: input.sensorFrame ?? null,
    captured_at: input.capturedAt ?? null,
    indexed_at: input.indexedAt ?? now,
    visibility: input.visibility ?? "public",
    safety_label: input.safetyLabel ?? null,
    metadata_json: input.metadataJson ?? null,
    created_at: now,
  };
}

export function toEmbedding768Row(input: Embedding768Input): Embedding768Row {
  const now = new Date().toISOString();

  return {
    embedding_id: input.embeddingId,
    source_uri: input.sourceUri,
    chunk_id: input.chunkId ?? null,
    source_vertex_id: input.sourceVertexId ?? null,
    tenant_id: input.tenantId ?? "public",
    shard_id: input.shardId ?? null,
    modality: input.modality,
    model_id: input.modelId,
    space_id: etzhayyim_MM_768_SPACE_ID,
    model_version: input.modelVersion ?? "initial",
    projection_id: input.projectionId,
    emb: vectorLiteral(input.vector),
    text_preview: input.textPreview ?? null,
    created_at: input.createdAt ?? now,
    embedded_at: input.embeddedAt ?? now,
  };
}
