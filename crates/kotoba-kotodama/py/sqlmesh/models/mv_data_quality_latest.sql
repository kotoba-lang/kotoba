-- Latest data quality snapshot per (repo, collection) via MAX(snapshot_date) join.
MODEL (
  name dev.mv_data_quality_latest,
  kind FULL,
  dialect postgres,
  description 'Latest data quality snapshot per repo × collection from vertex_data_quality_daily.',
  grain [repo, collection],
  tags [data_quality, monitoring]
);

WITH last_day AS (
  SELECT
    repo,
    collection,
    MAX(snapshot_date) AS snapshot_date
  FROM vertex_data_quality_daily
  GROUP BY repo, collection
)
SELECT d.*
FROM vertex_data_quality_daily d
JOIN last_day l
  ON d.repo        = l.repo
 AND d.collection  = l.collection
 AND d.snapshot_date = l.snapshot_date
