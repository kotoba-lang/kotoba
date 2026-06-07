-- Mangaka children by parent: per-parent edge counts grouped by child label.
MODEL (
  name dev.mv_mangaka_children_by_parent,
  kind FULL,
  dialect postgres,
  description 'Per (parent_vid, child_label): containment edge count from edge_contains.',
  grain [parent_vid, child_label],
  tags [mangaka, hierarchy, contains]
);

SELECT
  src_vid AS parent_vid,
  COALESCE(label, '') AS child_label,
  COUNT(*)::BIGINT AS cnt
FROM edge_contains
GROUP BY src_vid, COALESCE(label, '')
