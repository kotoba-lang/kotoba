-- HuggingFace Hub ingest progress: percent complete per dataset split cursor.
MODEL (
  name dev.mv_hfhub_ingest_progress,
  kind FULL,
  dialect postgres,
  description 'Per (repo_id, config_name, split_name): ingest cursor progress vs total rows, pct_complete.',
  grain [repo_id, config_name, split_name],
  tags [hfhub, ingest, progress]
);

SELECT
  c.repo_id,
  c.config_name,
  c.split_name,
  c.last_offset,
  c.total_emitted,
  s.num_rows,
  CASE WHEN s.num_rows > 0
       THEN ROUND(100.0 * c.last_offset / s.num_rows, 1)
       ELSE 0
  END AS pct_complete,
  c.updated_at
FROM vertex_hfhub_ingest_cursor c
LEFT JOIN vertex_hfhub_split s
  ON s.repo_id = c.repo_id
  AND s.config_name = c.config_name
  AND s.split_name = c.split_name
