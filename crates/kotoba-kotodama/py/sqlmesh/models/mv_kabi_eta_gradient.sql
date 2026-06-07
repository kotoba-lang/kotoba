-- ADR-2605080500: SQLMesh Phase 0 source-of-truth for mv_kabi_eta_gradient
-- Per-agent inbound hypha flow + eta gradient for PoNF gate decisions.
MODEL (
  name dev.mv_kabi_eta_gradient,
  kind FULL,
  dialect postgres,
  description 'Inbound hypha flow and eta gradient per destination agent (pruned_at IS NULL).',
  grain [agent_did],
  tags [organism, kabi, myco_yeast, ponf, materialized_view, adr_2605080500]
);

SELECT
  dst_agent_did      AS agent_did,
  COUNT(*)::BIGINT   AS inbound_count,
  SUM(flow)          AS inbound_flow,
  AVG(eta)           AS inbound_eta_avg,
  MAX(eta)           AS inbound_eta_max
FROM edge_kabi_hypha
WHERE pruned_at IS NULL
GROUP BY dst_agent_did
