-- Kami flow node label counts: alive node counts per repo and node label.
MODEL (
  name dev.mv_kami_flow_node_label_counts,
  kind FULL,
  dialect postgres,
  description 'Per (repo, node_label): node count from vertex_kami_flow_node where _alive is not false.',
  grain [repo, node_label],
  tags [kami, flow, node, label]
);

SELECT
  repo,
  node_label,
  COUNT(*) AS cnt
FROM vertex_kami_flow_node
WHERE _alive IS DISTINCT FROM FALSE
GROUP BY repo, node_label
