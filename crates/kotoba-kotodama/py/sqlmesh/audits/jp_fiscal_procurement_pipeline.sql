-- SQLMesh audit: mv_jp_fiscal_procurement_pipeline_coverage invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_jp_fiscal_procurement_subset_counts_le_bid,
  model dev.mv_jp_fiscal_procurement_pipeline_coverage,
  dialect postgres,
  description 'All bid_with_*_count fields must not exceed bid_count.'
);
SELECT *
FROM dev.mv_jp_fiscal_procurement_pipeline_coverage
WHERE bid_with_document_count > bid_count
   OR evidenced_bid_count > bid_count
   OR awarded_bid_count > bid_count
   OR bid_with_awarded_amount_count > bid_count
   OR bid_with_contract_count > bid_count
   OR bid_with_contract_edge_count > bid_count;

---

AUDIT (
  name assert_jp_fiscal_procurement_amounts_nonnegative,
  model dev.mv_jp_fiscal_procurement_pipeline_coverage,
  dialect postgres,
  description 'awarded_amount_total_jpy and contract_amount_total_jpy must be >= 0.'
);
SELECT *
FROM dev.mv_jp_fiscal_procurement_pipeline_coverage
WHERE awarded_amount_total_jpy < 0
   OR contract_amount_total_jpy < 0;
