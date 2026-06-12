-- Open LEI GLEIF ingest status: GLEIF file vs shard ingest progress per dataset.
MODEL (
  name dev.mv_open_lei_gleif_ingest_status,
  kind FULL,
  dialect postgres,
  description 'Per (dataset_kind, as_of_date): file/shard counts, expected/actual records, error counts.',
  grain [dataset_kind, as_of_date],
  tags [open_lei, gleif, ingest, status]
);

SELECT
  f.dataset_kind,
  f.as_of_date,
  COUNT(DISTINCT f.vertex_id) AS file_count,
  SUM(f.record_count) AS expected_record_count,
  COUNT(DISTINCT s.vertex_id) AS shard_count,
  SUM(s.records_read) AS records_read,
  SUM(s.records_written) AS records_written,
  SUM(s.error_count) AS error_count,
  MAX(f._seq) AS _seq
FROM vertex_open_lei_gleif_file f
LEFT JOIN vertex_open_lei_gleif_shard s ON s.file_id = f.file_id
GROUP BY f.dataset_kind, f.as_of_date
