-- JP fiscal record-document coverage: per-record document linkage across budget/appropriation/procurement.
MODEL (
  name dev.mv_jp_fiscal_record_document_coverage,
  kind FULL,
  dialect postgres,
  description 'Per fiscal record: document SHA, media type, byte length, and evidence edge presence.',
  grain [collection, vertex_id],
  tags [jp_fiscal, record, document, coverage]
);

SELECT
  records.collection,
  records.vertex_id,
  records.fiscal_year,
  records.account_type,
  records.doc_type,
  records.program_code,
  records.amount_jpy,
  records.source_id,
  records.document_id,
  d.sha256 AS document_sha256,
  d.media_type AS document_media_type,
  d.byte_length AS document_byte_length,
  CASE WHEN records.document_id IS NULL THEN FALSE ELSE TRUE END AS has_document_id,
  CASE WHEN d.vertex_id IS NULL THEN FALSE ELSE TRUE END AS has_document_vertex,
  CASE WHEN e.edge_id IS NULL THEN FALSE ELSE TRUE END AS has_record_evidence_edge,
  e.confidence AS record_evidence_confidence
FROM (
  SELECT
    'com.etzhayyim.apps.jpFiscal.budgetBook' AS collection,
    vertex_id,
    fiscal_year,
    account_type,
    doc_type,
    NULL::VARCHAR AS program_code,
    total_jpy AS amount_jpy,
    source_id,
    document_id
  FROM vertex_jp_fiscal_budget_book
  UNION ALL
  SELECT
    'com.etzhayyim.apps.jpFiscal.appropriation' AS collection,
    vertex_id,
    fiscal_year,
    account_type,
    doc_type,
    program_code,
    amount_jpy,
    source_id,
    document_id
  FROM vertex_jp_fiscal_appropriation
  UNION ALL
  SELECT
    'com.etzhayyim.apps.jpFiscal.procurementBid' AS collection,
    vertex_id,
    CASE
      WHEN EXTRACT(MONTH FROM opened_at) >= 4 THEN EXTRACT(YEAR FROM opened_at)::INT
      ELSE EXTRACT(YEAR FROM opened_at)::INT - 1
    END AS fiscal_year,
    'unknown'::VARCHAR AS account_type,
    'announcement'::VARCHAR AS doc_type,
    tender_no AS program_code,
    estimated_jpy AS amount_jpy,
    source_id,
    document_id
  FROM vertex_jp_fiscal_procurement_bid
) records
LEFT JOIN vertex_jp_fiscal_document d ON d.vertex_id = records.document_id
LEFT JOIN edge_jp_fiscal_evidence e
  ON e.src_vid = records.document_id
  AND e.dst_vid = records.vertex_id
  AND e.evidence_kind = 'DOCUMENT_SUPPORTS_RECORD'
