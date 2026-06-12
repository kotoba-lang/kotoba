-- Animeka child entity count per parent vertex and child label.
MODEL (
  name dev.mv_animeka_children_by_parent,
  kind FULL,
  dialect postgres,
  description 'Count of child entities per parent vertex from edge_contains, grouped by child label.',
  grain [parent_vid, child_label],
  tags [animeka, children, parent, edge_contains]
);

SELECT
  src_vid AS parent_vid,
  COALESCE(label, '') AS child_label,
  COUNT(*)::BIGINT AS cnt
FROM edge_contains
GROUP BY 1, 2
