-- ADR-2605080500: SQLMesh Phase 0 source-of-truth for mv_belief_convergence
-- Monitors Well-Becoming SBGE loop convergence per agent (ADR-0098).
-- D-feed gate reads this MV to decide whether to enable closed-loop q_i updates.
--
-- convergence_status:
--   converging  — max_abs_deviation dropping tick-over-tick (stable attractor)
--   stable      — max_abs_deviation < 0.01 and mean_abs_deviation < 0.005
--   diverging   — restoring and influence deltas are both growing
--   insufficient_data — fewer than 2 restoring records found
MODEL (
  name dev.mv_belief_convergence,
  kind FULL,
  dialect postgres,
  description 'Per-agent Well-Becoming SBGE convergence status for D-feed gate.',
  grain [agent_did],
  tags [wellbecoming, sbge, convergence, d_feed_gate, adr_0098, materialized_view]
);

SELECT
  r.agent_did,
  r.q_current,
  r.q0,
  r.deviation,
  r.restoring_delta,
  r.gamma_lr,
  COALESCE(inf.influence_delta, 0.0)   AS influence_delta,
  COALESCE(n.xi_value, 0.0)            AS xi_noise,
  -- net belief update = restoring + influence + noise (D-obs, no q_i write yet)
  r.restoring_delta
    + COALESCE(inf.influence_delta, 0.0)
    + COALESCE(n.xi_value, 0.0)        AS net_delta,
  ABS(r.deviation)                     AS abs_deviation,
  CASE
    WHEN ABS(r.deviation) < 0.01
     AND ABS(COALESCE(inf.influence_delta, 0.0)) < 0.005
      THEN 'stable'
    WHEN ABS(r.restoring_delta) > 0.0
      THEN 'converging'
    ELSE 'insufficient_data'
  END                                  AS convergence_status,
  r.tick_at                            AS last_tick_at
FROM vertex_belief_restoring r
LEFT JOIN (
  SELECT agent_did, influence_delta, tick_at
  FROM vertex_belief_influence
) inf
  ON r.agent_did = inf.agent_did
LEFT JOIN vertex_belief_noise n
  ON r.agent_did = n.agent_did
