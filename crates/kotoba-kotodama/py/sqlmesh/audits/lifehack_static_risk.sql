-- SQLMesh audit: mv_lifehack_static_risk_now invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_lifehack_humidity_below_filter,
  model dev.mv_lifehack_static_risk_now,
  dialect postgres,
  description 'min_humidity_pct must be < 40 (WHERE clause filters humidity_pct < 40).'
);
SELECT *
FROM dev.mv_lifehack_static_risk_now
WHERE min_humidity_pct >= 40.0;

---

AUDIT (
  name assert_lifehack_reading_count_positive,
  model dev.mv_lifehack_static_risk_now,
  dialect postgres,
  description 'reading_count must be > 0 (group rows imply at least one reading).'
);
SELECT *
FROM dev.mv_lifehack_static_risk_now
WHERE reading_count <= 0;
