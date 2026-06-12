-- Kami flow relation label counts: alive edge counts per repo and relation label.
MODEL (
  name dev.mv_kami_flow_relation_label_counts,
  kind FULL,
  dialect postgres,
  description 'Per (repo, relation_label): edge count from edge_kami_flow_relation where _alive is not false.',
  grain [repo, relation_label],
  tags [kami, flow, relation, label]
);

SELECT
  repo,
  relation_label,
  COUNT(*) AS cnt
FROM edge_kami_flow_relation
WHERE _alive IS DISTINCT FROM FALSE
GROUP BY repo, relation_label
