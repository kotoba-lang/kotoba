-- HuggingFace Hub library popularity: model count and downloads per library.
MODEL (
  name dev.mv_hfhub_library_popularity,
  kind FULL,
  dialect postgres,
  description 'Per library_name: model count, total downloads, and max downloads.',
  grain [library_name],
  tags [hfhub, library, popularity, downloads]
);

SELECT
  library_name,
  COUNT(*) AS model_count,
  SUM(downloads_month) AS total_downloads,
  MAX(downloads_month) AS max_downloads
FROM vertex_hfhub_model
WHERE library_name IS NOT NULL
GROUP BY library_name
