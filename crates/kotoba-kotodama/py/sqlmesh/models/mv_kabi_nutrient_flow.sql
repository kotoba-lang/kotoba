-- ADR-2605080500: SQLMesh Phase 0 source-of-truth for mv_kabi_nutrient_flow
-- Mycelial network hypha edge aggregate: flow and eta per agent pair.
MODEL (
  name dev.mv_kabi_nutrient_flow,
  kind FULL,
  dialect postgres,
  description 'Aggregate hypha count, total flow, and avg eta per agent pair (pruned_at IS NULL).',
  grain [src_agent_did, dst_agent_did],
  tags [organism, kabi, myco_yeast, materialized_view, adr_2605080500]
);

SELECT
  src_agent_did,
  dst_agent_did,
  COUNT(*)::BIGINT   AS hypha_count,
  SUM(flow)          AS total_flow,
  AVG(eta)           AS avg_eta
FROM edge_kabi_hypha
WHERE pruned_at IS NULL
GROUP BY src_agent_did, dst_agent_did
