-- Infer cluster summary: input counts per batch and cluster label.
MODEL (
  name dev.mv_infer_cluster_summary,
  kind FULL,
  dialect postgres,
  description 'Per (batch_id, label): input count from vertex_infer_input.',
  grain [batch_id, label],
  tags [infer, cluster, summary]
);

SELECT
  batch_id,
  label,
  COUNT(*) AS input_count
FROM vertex_infer_input
GROUP BY batch_id, label
