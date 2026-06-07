-- Belief noise summary: aggregate xi statistics across all agents.
MODEL (
  name dev.mv_belief_noise_summary,
  kind FULL,
  dialect postgres,
  description 'Aggregate belief noise statistics: mean xi, mean |xi|, max |xi|, mean xi^2, latest tick.',
  grain [],
  tags [belief, noise, xi, statistics]
);

SELECT
  COUNT(*) AS n_agents,
  AVG(xi_value) AS mean_xi,
  AVG(CASE WHEN xi_value >= 0 THEN xi_value ELSE -xi_value END) AS mean_abs_xi,
  MAX(CASE WHEN xi_value >= 0 THEN xi_value ELSE -xi_value END) AS max_abs_xi,
  AVG(xi_value * xi_value) AS mean_xi_sq,
  MAX(tick_ms) AS latest_tick_ms
FROM vertex_belief_noise
