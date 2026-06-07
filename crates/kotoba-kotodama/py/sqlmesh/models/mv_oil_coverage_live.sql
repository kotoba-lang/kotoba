-- Oil coverage live: per-target coverage rate computed against backbone counts.
MODEL (
  name dev.mv_oil_coverage_live,
  kind FULL,
  dialect postgres,
  description 'Per oil coverage target: target vs actual count, coverage_rate, and coverage_gap.',
  grain [target_key],
  tags [oil, coverage, live]
);

SELECT
  t.target_key,
  t.country_code,
  t.segment,
  t.actor_did,
  t.app,
  t.target_count,
  t.priority,
  COALESCE(b.actual_count, 0) AS actual_count,
  CASE
    WHEN t.target_count > 0 THEN COALESCE(b.actual_count, 0)::DOUBLE PRECISION / t.target_count::DOUBLE PRECISION
    ELSE 0.0
  END AS coverage_rate,
  GREATEST(t.target_count - COALESCE(b.actual_count, 0), 0) AS coverage_gap
FROM dim_oil_coverage_target t
LEFT JOIN dev.mv_oil_backbone_count b
  ON b.country_code = t.country_code
  AND b.segment = t.segment
