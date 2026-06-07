-- Organizer classification category counts: item counts per (org, category, subcategory).
MODEL (
  name dev.mv_organizer_classification_category_counts,
  kind FULL,
  dialect postgres,
  description 'Per (org_id, category, subcategory): item count and avg confidence.',
  grain [org_id, category, subcategory],
  tags [organizer, classification, counts]
);

SELECT
  org_id,
  category,
  subcategory,
  COUNT(*)::BIGINT AS item_count,
  AVG(confidence) AS avg_confidence
FROM vertex_organizer_classification
GROUP BY org_id, category, subcategory
