-- SQLMesh audit: mv_jp_fiscal_budget_pipeline_coverage invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_jp_fiscal_budget_match_consistency,
  model dev.mv_jp_fiscal_budget_pipeline_coverage,
  dialect postgres,
  description 'When appropriation_total_matches_budget=true, sums must actually equal.'
);
SELECT *
FROM dev.mv_jp_fiscal_budget_pipeline_coverage
WHERE appropriation_total_matches_budget = TRUE
  AND appropriation_total_jpy <> budget_total_jpy;

---

AUDIT (
  name assert_jp_fiscal_budget_counts_nonnegative,
  model dev.mv_jp_fiscal_budget_pipeline_coverage,
  dialect postgres,
  description 'All count and total fields must be >= 0.'
);
SELECT *
FROM dev.mv_jp_fiscal_budget_pipeline_coverage
WHERE appropriation_count < 0
   OR appropriation_total_jpy < 0
   OR appropriation_flow_count < 0
   OR appropriation_flow_total_jpy < 0
   OR document_record_evidence_count < 0;
