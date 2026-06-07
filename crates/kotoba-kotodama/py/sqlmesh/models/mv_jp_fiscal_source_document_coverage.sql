-- JP fiscal source-document coverage: per source registration vs fetched document.
MODEL (
  name dev.mv_jp_fiscal_source_document_coverage,
  kind FULL,
  dialect postgres,
  description 'Per source: registered URL vs fetched document with SHA, byte length, and evidence edge presence.',
  grain [source_id],
  tags [jp_fiscal, source, document, coverage]
);

SELECT
  s.source_id,
  s.collection,
  s.title,
  s.publisher_did,
  s.source_url AS registered_source_url,
  s.access_kind,
  s.cadence,
  s.status AS source_status,
  d.vertex_id AS document_vertex_id,
  d.source_url AS fetched_source_url,
  d.fetched_at,
  d.media_type,
  d.sha256,
  d.byte_length,
  CASE WHEN d.vertex_id IS NULL THEN FALSE ELSE TRUE END AS fetched,
  CASE WHEN e.edge_id IS NULL THEN FALSE ELSE TRUE END AS has_evidence_edge
FROM vertex_jp_fiscal_source s
LEFT JOIN vertex_jp_fiscal_document d ON d.source_id = s.source_id
LEFT JOIN edge_jp_fiscal_evidence e
  ON e.src_vid = s.vertex_id
  AND e.dst_vid = d.vertex_id
  AND e.evidence_kind = 'SOURCE_DOCUMENT'
