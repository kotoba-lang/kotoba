# etzhayyim-project-vector-embedding

etzhayyim search embedding project for text, image, video, audio, and future
sensor-inclusive retrieval.

The current schema owner is:

- `30-graph/graph-schema/migrations/20260427001000_vector_embedding_project_tables.ts`

Phase 1 stores only one production vector shape:

- `etzhayyim-mm-768` for text, image, video, audio, depth, thermal, IMU, and other
  future sensor modalities.

Initial source models are BGE-M3 for text, OpenCLIP for image/text candidates,
and Qwen3-VL-Embedding for image, screenshot, video, text, and mixed-input
retrieval. Their native dimensions are recorded in the model registry, but
workers must project, truncate, or distill embeddings into 768d before inserting
into RisingWave.

RisingWave stores all Phase 1 vectors in `vertex_vector_embedding_768`. Raw
model output is not stored in separate vector tables. Later projection jobs can
write new rows into the same 768d table with a new `projection_id` and
`model_version` without rewriting source/chunk metadata.

Hume AI Expression Measurement is stored as non-vector enrichment in
`vertex_vector_emotion_signal`. The Hume `hume-emotional-language` signal is
keyed by the same `source_uri` as the 768d embedding row, so retrieval can later
combine semantic distance with emotion filters or reranking without mixing
emotion scores into the vector space.

Worker contract:

- `src/model-catalog.ts` chooses the default model per modality.
- `src/projection.ts` converts native model output into normalized 768d.
- `src/job.ts` builds source and embedding rows from one embedding job.
- `src/sql.ts` builds parameterized inserts for RisingWave.
- `src/search.ts` builds the routed HNSW search query for
  `vertex_vector_embedding_768`.

The current projection rules are intentionally conservative placeholders:
BGE-M3 and Qwen3-VL vectors are truncated to 768d, OpenCLIP vectors are padded
to 768d, and all results are L2-normalized. Replace these with trained adapters
or MRL-native output before large-scale backfill.

Operational rollout is documented in `RUNBOOK.md`.
