-- SQLMesh model: mv_canopy_shape
-- Bonsai growth canopy shape MV (ADR-2605080100).
-- Source of truth for deployed RisingWave CREATE MATERIALIZED VIEW.

MODEL (
  name dev.mv_canopy_shape,
  kind FULL,
  dialect postgres,
  description 'Bonsai canopy shape — live actor η-score distribution for growth/prune decisions.',
  grain [actor_did],
  tags [bonsai, growth, materialized_view]
);

SELECT
  actor_did,
  SUM(total_flow)                        AS canopy_total_flow,
  MIN(eta_score)                         AS canopy_min_eta,
  AVG(eta_score)                         AS canopy_avg_eta,
  COUNT(*)                               AS branch_count,
  MAX(updated_at)                        AS last_updated_at
FROM graphar.vertex_growth_event
WHERE status != 'dormant'
GROUP BY 1
