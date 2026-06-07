-- SQLMesh audit: mv_open_smartphone_sep_risk_summary invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_smartphone_sep_subset_counts_le_total,
  model dev.mv_open_smartphone_sep_risk_summary,
  dialect postgres,
  description 'frand_count, pooled_count, expiring_24m must not exceed total_seps.'
);
SELECT *
FROM dev.mv_open_smartphone_sep_risk_summary
WHERE frand_count > total_seps
   OR pooled_count > total_seps
   OR expiring_24m > total_seps;

---

AUDIT (
  name assert_smartphone_sep_pool_fee_ordered,
  model dev.mv_open_smartphone_sep_risk_summary,
  dialect postgres,
  description 'min_pool_fee_usd must not exceed max_pool_fee_usd (when both non-null).'
);
SELECT *
FROM dev.mv_open_smartphone_sep_risk_summary
WHERE min_pool_fee_usd IS NOT NULL
  AND max_pool_fee_usd IS NOT NULL
  AND min_pool_fee_usd > max_pool_fee_usd;
