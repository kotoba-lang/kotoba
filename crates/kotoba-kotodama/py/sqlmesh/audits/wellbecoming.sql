-- Well-Becoming MV audits: bottleneck_caller, at_risk, score_actor, entropy_trend
-- ADR-2604291800

AUDIT (
  name assert_bottleneck_caller_nonneg_event_count,
  model dev.mv_wellbecoming_bottleneck_caller
)
SELECT * FROM dev.mv_wellbecoming_bottleneck_caller WHERE event_count <= 0;

AUDIT (
  name assert_bottleneck_caller_nonneg_floor_violations,
  model dev.mv_wellbecoming_bottleneck_caller
)
SELECT * FROM dev.mv_wellbecoming_bottleneck_caller WHERE floor_violations < 0;

AUDIT (
  name assert_at_risk_separation_delta_or_floor,
  model dev.mv_wellbecoming_at_risk
)
SELECT * FROM dev.mv_wellbecoming_at_risk
WHERE NOT (avg_separation_delta < -0.3 OR floor_violations > 0);

AUDIT (
  name assert_score_actor_nonneg_event_count,
  model dev.mv_wellbecoming_score_actor
)
SELECT * FROM dev.mv_wellbecoming_score_actor WHERE event_count <= 0;

AUDIT (
  name assert_score_actor_nonneg_floor_violations,
  model dev.mv_wellbecoming_score_actor
)
SELECT * FROM dev.mv_wellbecoming_score_actor WHERE floor_violations < 0;

AUDIT (
  name assert_entropy_trend_nonneg_event_count,
  model dev.mv_wellbecoming_entropy_trend
)
SELECT * FROM dev.mv_wellbecoming_entropy_trend WHERE event_count <= 0;

AUDIT (
  name assert_entropy_trend_nonneg_floor_violations,
  model dev.mv_wellbecoming_entropy_trend
)
SELECT * FROM dev.mv_wellbecoming_entropy_trend WHERE floor_violations < 0;
