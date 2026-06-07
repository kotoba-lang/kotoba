-- Audits for mv_attractor_stability, mv_attractor_stability_by_agent,
-- and mv_belief_restoring_summary (ADR-0098 Repo-as-Attractor).

AUDIT (
  name assert_attractor_stability_valid_status,
  model dev.mv_attractor_stability
)
SELECT *
FROM dev.mv_attractor_stability
WHERE attractor_status NOT IN ('stable', 'converging', 'diverging');

AUDIT (
  name assert_attractor_stability_entropy_spread_nonneg,
  model dev.mv_attractor_stability
)
SELECT *
FROM dev.mv_attractor_stability
WHERE entropy_spread < 0;

AUDIT (
  name assert_attractor_stability_floor_violation_rate_bounded,
  model dev.mv_attractor_stability
)
SELECT *
FROM dev.mv_attractor_stability
WHERE floor_violation_rate < 0 OR floor_violation_rate > 1;

AUDIT (
  name assert_attractor_by_agent_entropy_spread_nonneg,
  model dev.mv_attractor_stability_by_agent
)
SELECT *
FROM dev.mv_attractor_stability_by_agent
WHERE entropy_spread < 0;

AUDIT (
  name assert_attractor_by_agent_valid_status,
  model dev.mv_attractor_stability_by_agent
)
SELECT *
FROM dev.mv_attractor_stability_by_agent
WHERE attractor_status NOT IN ('stable', 'converging', 'diverging');

AUDIT (
  name assert_belief_restoring_summary_valid_status,
  model dev.mv_belief_restoring_summary
)
SELECT *
FROM dev.mv_belief_restoring_summary
WHERE deviation_status NOT IN ('at_baseline', 'near_baseline', 'drifting');

AUDIT (
  name assert_belief_restoring_summary_deviations_nonneg,
  model dev.mv_belief_restoring_summary
)
SELECT *
FROM dev.mv_belief_restoring_summary
WHERE max_abs_deviation < 0 OR mean_abs_deviation < 0;
