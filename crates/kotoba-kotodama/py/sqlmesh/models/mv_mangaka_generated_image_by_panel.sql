-- Mangaka generated image by panel: generated image edge count per panel.
MODEL (
  name dev.mv_mangaka_generated_image_by_panel,
  kind FULL,
  dialect postgres,
  description 'Per panel_vid: count of generatedImage edges from edge_contains.',
  grain [panel_vid],
  tags [mangaka, panel, generated_image]
);

SELECT
  src_vid AS panel_vid,
  COUNT(*)::BIGINT AS cnt
FROM edge_contains
WHERE COALESCE(label, '') = 'generatedImage'
GROUP BY src_vid
