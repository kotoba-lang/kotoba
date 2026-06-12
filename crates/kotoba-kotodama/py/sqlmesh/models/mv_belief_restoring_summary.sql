-- ADR-0098 Repo-as-Attractor: γ restoring force convergence summary.
-- deviation_status drives D-feed gate: 'at_baseline' | 'near_baseline' | 'drifting'.
MODEL (
  name dev.mv_belief_restoring_summary,
  kind FULL,
  dialect postgres,
  description 'Global restoring force status: max/mean deviation and restoring_delta across all agents.',
  tags [wellbecoming, belief, attractor, restoring, sbge, adr_0098]
);

SELECT
  MAX(ABS(deviation))       AS max_abs_deviation,
  AVG(ABS(deviation))       AS mean_abs_deviation,
  MAX(ABS(restoring_delta)) AS max_abs_restoring,
  AVG(ABS(restoring_delta)) AS mean_abs_restoring,
  SUM(CASE WHEN ABS(deviation) < 0.01 THEN 1 ELSE 0 END) AS n_at_baseline,
  COUNT(*)                  AS n_agents,
  CASE
    WHEN MAX(ABS(deviation)) < 0.01 THEN 'at_baseline'
    WHEN MAX(ABS(deviation)) < 0.05 THEN 'near_baseline'
    ELSE 'drifting'
  END                       AS deviation_status
FROM vertex_belief_restoring
