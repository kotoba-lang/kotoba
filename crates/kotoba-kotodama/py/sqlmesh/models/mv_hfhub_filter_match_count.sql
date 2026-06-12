-- HuggingFace Hub filter match count: dataset count per filter.
MODEL (
  name dev.mv_hfhub_filter_match_count,
  kind FULL,
  dialect postgres,
  description 'Per filter_id: distinct dataset count from edge_hfhub_filter_match.',
  grain [filter_id],
  tags [hfhub, filter, dataset, count]
);

SELECT
  filter_id,
  COUNT(DISTINCT dataset_id) AS dataset_count
FROM edge_hfhub_filter_match
GROUP BY filter_id
