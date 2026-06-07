-- SQLMesh audit: mv_yadoya_chain_coverage invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_yadoya_chain_hotel_count_positive,
  model dev.mv_yadoya_chain_coverage,
  dialect postgres,
  description 'hotel_count must be > 0 (group rows imply at least one published hotel).'
);
SELECT *
FROM dev.mv_yadoya_chain_coverage
WHERE hotel_count <= 0;

---

AUDIT (
  name assert_yadoya_chain_did_normalized,
  model dev.mv_yadoya_chain_coverage,
  dialect postgres,
  description 'chain_did must never be NULL (COALESCE to "independent" applied).'
);
SELECT *
FROM dev.mv_yadoya_chain_coverage
WHERE chain_did IS NULL;
