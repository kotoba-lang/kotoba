-- Project child count: per-parent project child count rollup.
MODEL (
  name dev.mv_project_child_count,
  kind FULL,
  dialect postgres,
  description 'Per parent_id: count of child project records from vertex_project_props.',
  grain [parent_id],
  tags [project, child, count]
);

SELECT
  parent_id,
  COUNT(*)::BIGINT AS cnt
FROM vertex_project_props
WHERE parent_id IS NOT NULL
GROUP BY parent_id
