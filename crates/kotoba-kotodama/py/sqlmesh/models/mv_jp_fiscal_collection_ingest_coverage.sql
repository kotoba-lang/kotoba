-- JP fiscal collection ingest coverage: source document fetch and evidence counts per collection.
MODEL (
  name dev.mv_jp_fiscal_collection_ingest_coverage,
  kind FULL,
  dialect postgres,
  description 'Per collection: source count, fetched count, evidenced count, total bytes.',
  grain [collection],
  tags [jp_fiscal, collection, ingest, coverage]
);

SELECT
  collection,
  COUNT(*) AS source_count,
  SUM(CASE WHEN fetched THEN 1 ELSE 0 END) AS fetched_source_count,
  SUM(CASE WHEN has_evidence_edge THEN 1 ELSE 0 END) AS evidenced_source_count,
  SUM(COALESCE(byte_length, 0)) AS fetched_bytes
FROM dev.mv_jp_fiscal_source_document_coverage
GROUP BY collection
