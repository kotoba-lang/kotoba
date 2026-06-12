-- Telecom SCP discovery load: SCP discovery aggregates per target/strategy.
MODEL (
  name dev.mv_telecom_scp_discovery_load,
  kind FULL,
  dialect postgres,
  description 'Per (target_nf_type, selection_strategy): avg candidate count and discovery count.',
  grain [target_nf_type, selection_strategy],
  tags [telecom, 5g, scp, discovery]
);

SELECT
  target_nf_type,
  selection_strategy,
  AVG(candidate_count) AS avg_candidate_count,
  COUNT(*) AS discovery_count
FROM vertex_telecom_scp_discovery
GROUP BY target_nf_type, selection_strategy
