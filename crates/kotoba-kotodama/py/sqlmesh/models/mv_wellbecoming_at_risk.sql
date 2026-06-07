-- ADR-2604291800 Well-Becoming: at-risk callers needing proactive outreach.
-- Derived from mv_wellbecoming_bottleneck_caller: separation_delta < -0.3 OR floor_violations > 0.
MODEL (
  name dev.mv_wellbecoming_at_risk,
  kind FULL,
  dialect postgres,
  description 'At-risk callers: avg_separation_delta < -0.3 or floor_violations > 0.',
  grain [caller_did],
  tags [wellbecoming, at_risk, adr_2604291800]
);

SELECT
  caller_did,
  avg_separation_delta,
  avg_spirit,
  avg_total,
  floor_violations,
  last_activity_at
FROM dev.mv_wellbecoming_bottleneck_caller
WHERE avg_separation_delta < -0.3
   OR floor_violations > 0
