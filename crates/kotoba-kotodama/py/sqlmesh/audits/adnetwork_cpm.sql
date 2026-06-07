-- SQLMesh audit: mv_open_adnetwork_market_cpm_range invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_adnetwork_cpm_ordered,
  model dev.mv_open_adnetwork_market_cpm_range,
  dialect postgres,
  description 'min_floor_cpm <= avg_floor_cpm <= max_floor_cpm.'
);
SELECT *
FROM dev.mv_open_adnetwork_market_cpm_range
WHERE min_floor_cpm > avg_floor_cpm
   OR avg_floor_cpm > max_floor_cpm;

---

AUDIT (
  name assert_adnetwork_cpm_nonnegative,
  model dev.mv_open_adnetwork_market_cpm_range,
  dialect postgres,
  description 'min_floor_cpm must be >= 0.'
);
SELECT *
FROM dev.mv_open_adnetwork_market_cpm_range
WHERE min_floor_cpm < 0;
