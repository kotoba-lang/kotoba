-- JP fiscal budget pipeline coverage: budget book vs appropriation vs flow vs evidence completeness.
MODEL (
  name dev.mv_jp_fiscal_budget_pipeline_coverage,
  kind FULL,
  dialect postgres,
  description 'Per budget book: appropriation, flow, and evidence coverage with match flags.',
  grain [budget_book_vertex_id],
  tags [jp_fiscal, budget, pipeline, coverage]
);

SELECT
  b.vertex_id AS budget_book_vertex_id,
  b.fiscal_year,
  b.account_type,
  b.doc_type,
  b.total_jpy AS budget_total_jpy,
  COALESCE(a.appropriation_count, 0) AS appropriation_count,
  COALESCE(a.appropriation_total_jpy, 0) AS appropriation_total_jpy,
  COALESCE(f.appropriation_flow_count, 0) AS appropriation_flow_count,
  COALESCE(f.appropriation_flow_total_jpy, 0) AS appropriation_flow_total_jpy,
  COALESCE(e.document_record_evidence_count, 0) AS document_record_evidence_count,
  CASE WHEN COALESCE(a.appropriation_total_jpy, 0) = b.total_jpy THEN TRUE ELSE FALSE END AS appropriation_total_matches_budget,
  CASE WHEN COALESCE(f.appropriation_flow_total_jpy, 0) = b.total_jpy THEN TRUE ELSE FALSE END AS flow_total_matches_budget,
  CASE WHEN COALESCE(e.document_record_evidence_count, 0) = COALESCE(a.appropriation_count, 0) + 1 THEN TRUE ELSE FALSE END AS all_budget_records_evidenced
FROM vertex_jp_fiscal_budget_book b
LEFT JOIN (
  SELECT fiscal_year, account_type, doc_type, COUNT(*) AS appropriation_count, SUM(amount_jpy) AS appropriation_total_jpy
  FROM vertex_jp_fiscal_appropriation
  GROUP BY fiscal_year, account_type, doc_type
) a ON a.fiscal_year = b.fiscal_year AND a.account_type = b.account_type AND a.doc_type = b.doc_type
LEFT JOIN (
  SELECT src_vid, COUNT(*) AS appropriation_flow_count, SUM(amount_jpy) AS appropriation_flow_total_jpy
  FROM edge_jp_fiscal_flow
  WHERE flow_type = 'appropriation'
  GROUP BY src_vid
) f ON f.src_vid = b.vertex_id
LEFT JOIN (
  SELECT fiscal_year, account_type, doc_type, COUNT(*) AS document_record_evidence_count
  FROM dev.mv_jp_fiscal_record_document_coverage
  WHERE has_record_evidence_edge = TRUE
  GROUP BY fiscal_year, account_type, doc_type
) e ON e.fiscal_year = b.fiscal_year AND e.account_type = b.account_type AND e.doc_type = b.doc_type
