-- HuggingFace Hub model task stats: download and parameter stats per pipeline tag.
MODEL (
  name dev.mv_hfhub_model_task_stats,
  kind FULL,
  dialect postgres,
  description 'Per pipeline_tag: model count, total/avg downloads, avg/max parameters, total likes.',
  grain [pipeline_tag],
  tags [hfhub, model, task, downloads]
);

SELECT
  pipeline_tag,
  COUNT(*) AS model_count,
  SUM(downloads_month) AS total_downloads,
  AVG(downloads_month) AS avg_downloads,
  AVG(num_parameters) FILTER (WHERE num_parameters IS NOT NULL) AS avg_parameters,
  MAX(num_parameters) AS max_parameters,
  SUM(likes) AS total_likes
FROM vertex_hfhub_model
WHERE pipeline_tag IS NOT NULL
GROUP BY pipeline_tag
