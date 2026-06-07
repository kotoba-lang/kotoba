-- JP fiscal procurement pipeline coverage: bid pipeline metrics aggregated by issuer and method.
MODEL (
  name dev.mv_jp_fiscal_procurement_pipeline_coverage,
  kind FULL,
  dialect postgres,
  description 'Per (fiscal_year, issuer_did, method, source_id): bid count, document/contract evidence rates, awarded totals.',
  grain [fiscal_year, issuer_did, method, source_id],
  tags [jp_fiscal, procurement, pipeline, coverage]
);

SELECT
  fiscal_year,
  issuer_did,
  method,
  source_id,
  COUNT(*) AS bid_count,
  SUM(CASE WHEN has_document_vertex THEN 1 ELSE 0 END) AS bid_with_document_count,
  SUM(CASE WHEN has_document_evidence_edge THEN 1 ELSE 0 END) AS evidenced_bid_count,
  SUM(CASE WHEN awarded_at IS NOT NULL THEN 1 ELSE 0 END) AS awarded_bid_count,
  SUM(CASE WHEN awarded_amount_jpy IS NOT NULL THEN 1 ELSE 0 END) AS bid_with_awarded_amount_count,
  SUM(CASE WHEN has_contract_vertex THEN 1 ELSE 0 END) AS bid_with_contract_count,
  SUM(CASE WHEN has_contract_procurement_edge THEN 1 ELSE 0 END) AS bid_with_contract_edge_count,
  SUM(COALESCE(awarded_amount_jpy, 0)) AS awarded_amount_total_jpy,
  SUM(COALESCE(contract_amount_jpy, 0)) AS contract_amount_total_jpy
FROM dev.mv_jp_fiscal_procurement_bid_contract_coverage
GROUP BY fiscal_year, issuer_did, method, source_id
