-- SQLMesh audit: mv_legal_entity_disclosure_coverage invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_legal_entity_score_bounded,
  model dev.mv_legal_entity_disclosure_coverage,
  dialect postgres,
  description 'disclosure_coverage_score must be in [0, 1] (sum of 5 binary indicators / 5).'
);
SELECT *
FROM dev.mv_legal_entity_disclosure_coverage
WHERE disclosure_coverage_score < 0 OR disclosure_coverage_score > 1;

---

AUDIT (
  name assert_legal_entity_counts_nonnegative,
  model dev.mv_legal_entity_disclosure_coverage,
  dialect postgres,
  description 'All count fields must be >= 0.'
);
SELECT *
FROM dev.mv_legal_entity_disclosure_coverage
WHERE filings_count < 0
   OR fact_count < 0
   OR subsidiaries_count < 0
   OR trade_edge_count < 0;
