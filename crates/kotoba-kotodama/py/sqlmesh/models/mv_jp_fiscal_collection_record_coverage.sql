-- JP fiscal collection record coverage: record/document/evidence counts per collection.
MODEL (
  name dev.mv_jp_fiscal_collection_record_coverage,
  kind FULL,
  dialect postgres,
  description 'Per (collection, fiscal_year, account_type, doc_type): record count, document presence, and evidence counts.',
  grain [collection, fiscal_year, account_type, doc_type],
  tags [jp_fiscal, collection, record, coverage]
);

SELECT
  collection,
  fiscal_year,
  account_type,
  doc_type,
  COUNT(*) AS record_count,
  SUM(CASE WHEN has_document_id THEN 1 ELSE 0 END) AS record_with_document_id_count,
  SUM(CASE WHEN has_document_vertex THEN 1 ELSE 0 END) AS record_with_document_vertex_count,
  SUM(CASE WHEN has_record_evidence_edge THEN 1 ELSE 0 END) AS evidenced_record_count,
  SUM(amount_jpy) AS total_amount_jpy
FROM dev.mv_jp_fiscal_record_document_coverage
GROUP BY collection, fiscal_year, account_type, doc_type
