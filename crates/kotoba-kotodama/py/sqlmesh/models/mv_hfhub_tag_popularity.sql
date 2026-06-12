-- HuggingFace Hub tag popularity: dataset count per tag.
MODEL (
  name dev.mv_hfhub_tag_popularity,
  kind FULL,
  dialect postgres,
  description 'Per tag: dataset count from edge_hfhub_dataset_tag.',
  grain [tag],
  tags [hfhub, tag, dataset, popularity]
);

SELECT
  tag,
  COUNT(*) AS dataset_count
FROM edge_hfhub_dataset_tag
GROUP BY tag
