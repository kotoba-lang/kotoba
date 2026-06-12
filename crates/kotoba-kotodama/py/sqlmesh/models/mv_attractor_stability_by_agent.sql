-- ADR-0098 Repo-as-Attractor: per-agent belief convergence status.
-- Agent-level entropy_spread and floor_violations for W_ij trust-weight diagnostics.
MODEL (
  name dev.mv_attractor_stability_by_agent,
  kind FULL,
  dialect postgres,
  description 'Per-agent SBGE attractor stability: entropy_spread + floor_violations + attractor_status.',
  grain [agent_did],
  tags [wellbecoming, belief, attractor, sbge, adr_0098]
);

SELECT
  agent_did,
  SUM(CASE WHEN scored = true THEN 1 ELSE 0 END)                              AS scored_events,

  SQRT(GREATEST(
    AVG(CASE WHEN scored = true THEN score_total * score_total ELSE NULL END)
    - AVG(CASE WHEN scored = true THEN score_total ELSE NULL END)
    * AVG(CASE WHEN scored = true THEN score_total ELSE NULL END),
    0.0
  ))                                                                           AS entropy_spread,

  AVG(CASE WHEN scored = true THEN score_total ELSE NULL END)                 AS mean_score_total,
  AVG(CASE WHEN separation_delta IS NOT NULL THEN separation_delta ELSE NULL END) AS mean_separation_delta,
  SUM(CASE WHEN floor_violated = true THEN 1 ELSE 0 END)                      AS floor_violations,

  CASE
    WHEN SQRT(GREATEST(
           AVG(CASE WHEN scored = true THEN score_total * score_total ELSE NULL END)
           - AVG(CASE WHEN scored = true THEN score_total ELSE NULL END)
           * AVG(CASE WHEN scored = true THEN score_total ELSE NULL END),
           0.0
         )) < 0.05 THEN 'stable'
    WHEN SQRT(GREATEST(
           AVG(CASE WHEN scored = true THEN score_total * score_total ELSE NULL END)
           - AVG(CASE WHEN scored = true THEN score_total ELSE NULL END)
           * AVG(CASE WHEN scored = true THEN score_total ELSE NULL END),
           0.0
         )) < 0.15 THEN 'converging'
    ELSE 'diverging'
  END                                                                          AS attractor_status,

  MAX(created_at)                                                              AS last_event_at
FROM vertex_wellbecoming_event
GROUP BY agent_did
