-- ADR-2605080500: SQLMesh Phase 0 source-of-truth for mv_shosha_reaction_count_by_upstream
-- Active cross-actor reaction counts and average confidence by upstream DID and type.
MODEL (
  name dev.mv_shosha_reaction_count_by_upstream,
  kind FULL,
  dialect postgres,
  description 'Active reaction counts and avg confidence per upstream_did and reaction_type.',
  grain [upstream_did, reaction_type],
  tags [shosha, reactive, cross_actor, trading, materialized_view, adr_2605080500]
);

SELECT
  upstream_did,
  reaction_type,
  COUNT(*)                           AS reaction_count,
  AVG(COALESCE(confidence, 0))       AS avg_confidence
FROM vertex_shosha_reaction
WHERE status = 'active'
GROUP BY upstream_did, reaction_type
