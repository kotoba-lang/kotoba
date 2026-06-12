-- Per-agent max information abstraction height and node count per counterparty/kind.
MODEL (
  name dev.mv_agent_information_height,
  kind FULL,
  dialect postgres,
  description 'Max abstraction level and node count per agent_did, counterparty_ref, and info_kind.',
  grain [agent_did, counterparty_ref, info_kind],
  tags [agent, information, height, abstraction]
);

SELECT
  agent_did,
  counterparty_ref,
  info_kind,
  MAX(abstraction_level) AS max_information_height,
  COUNT(*)::BIGINT AS node_count
FROM vertex_agent_information_node
GROUP BY agent_did, counterparty_ref, info_kind
