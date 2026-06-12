-- PPTX slide stats: shape, text run, and image counts per slide.
MODEL (
  name dev.mv_pptx_slide_stats,
  kind FULL,
  dialect postgres,
  description 'Per (presentation_id, slide_id): shape count, text run count, image count, last seq.',
  grain [presentation_id, slide_id],
  tags [pptx, slide, shape, image]
);

SELECT
  s.presentation_id,
  s.slide_id,
  COUNT(DISTINCT sh.shape_id) AS shape_count,
  COUNT(DISTINCT tr.text_run_id) AS text_run_count,
  COUNT(DISTINCT im.image_id) AS image_count,
  MAX(GREATEST(COALESCE(s._seq, 0), COALESCE(sh._seq, 0), COALESCE(tr._seq, 0), COALESCE(im._seq, 0))) AS last_seq
FROM vertex_pptx_slide s
LEFT JOIN vertex_pptx_shape sh ON sh.slide_id = s.slide_id
LEFT JOIN vertex_pptx_text_run tr ON tr.slide_id = s.slide_id
LEFT JOIN vertex_pptx_image im ON im.slide_id = s.slide_id
WHERE s.slide_id IS NOT NULL
GROUP BY s.presentation_id, s.slide_id
