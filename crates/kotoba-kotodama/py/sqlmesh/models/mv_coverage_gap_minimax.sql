-- SQLMesh model: mv_coverage_gap_minimax
-- Drives Zeebe coverage.gap.ingest scheduling (ADR-2605080500).
--
-- Source of truth for the deployed RisingWave streaming MV.
-- Apply changes via: rw-health-gate.sh gate + psql DDL channel.
--
-- Lineage:
--   vertex_coverage_recipe
--   vertex_coverage_stats
--   → mv_coverage_gap_minimax

MODEL (
  name dev.mv_coverage_gap_minimax,
  kind FULL,
  dialect postgres,
  description 'Per-domain regret-ranked coverage gap. Drives Zeebe coverage.gap.ingest scheduling. recipe_kind=defer excluded.',
  grain [domain, authority_kind],
  tags [coverage, zeebe, scheduling, materialized_view]
);

SELECT
  r.domain,
  r.authority_kind,
  r.recipe_kind,
  r.source_url,
  r.llm_tier,
  r.langgraph_id,
  COALESCE(s.world_total,    r.world_total)  AS world_total,
  COALESCE(s.collected,      0)              AS collected,
  COALESCE(s.coverage_rate,  0.0)            AS coverage_rate,
  r.notes,
  CAST(COALESCE(s.world_total, r.world_total) AS DOUBLE)
    * (1.0 - COALESCE(s.coverage_rate, 0.0)) AS regret,
  r.created_at
FROM vertex_coverage_recipe AS r
LEFT JOIN vertex_coverage_stats AS s
  ON s.domain = r.domain
  AND s.authority_kind = r.authority_kind
WHERE r.recipe_kind <> 'defer'
ORDER BY regret DESC
