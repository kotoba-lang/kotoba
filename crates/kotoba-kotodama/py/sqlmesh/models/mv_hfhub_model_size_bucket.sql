-- HuggingFace Hub model size bucket: model count and downloads per parameter size range.
MODEL (
  name dev.mv_hfhub_model_size_bucket,
  kind FULL,
  dialect postgres,
  description 'Per parameter size bucket: model count, avg downloads, total downloads.',
  grain [size_bucket],
  tags [hfhub, model, size, parameters]
);

SELECT
  CASE
    WHEN num_parameters IS NULL THEN 'unknown'
    WHEN num_parameters < 1000000000 THEN 'n<1B'
    WHEN num_parameters < 7000000000 THEN '1B<n<7B'
    WHEN num_parameters < 13000000000 THEN '7B<n<13B'
    WHEN num_parameters < 35000000000 THEN '13B<n<35B'
    WHEN num_parameters < 70000000000 THEN '35B<n<70B'
    ELSE 'n>70B'
  END AS size_bucket,
  COUNT(*) AS model_count,
  AVG(downloads_month) AS avg_downloads,
  SUM(downloads_month) AS total_downloads
FROM vertex_hfhub_model
GROUP BY 1
