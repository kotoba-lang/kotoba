-- Scaffold item count by category: per-category scaffold item count.
MODEL (
  name dev.mv_scaffold_item_count_by_category,
  kind FULL,
  dialect postgres,
  description 'Per category: scaffold item count from vertex_ScaffoldItem.',
  grain [category],
  tags [scaffold, item, count]
);

SELECT
  COALESCE(category, '') AS category,
  COUNT(*)::BIGINT AS cnt
FROM "vertex_ScaffoldItem"
GROUP BY 1
