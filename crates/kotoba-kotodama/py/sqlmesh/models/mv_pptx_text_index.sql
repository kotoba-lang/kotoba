-- PPTX text index: concatenated text per slide for full-text search.
MODEL (
  name dev.mv_pptx_text_index,
  kind FULL,
  dialect postgres,
  description 'Per (presentation_id, slide_id): text run count, concatenated text, last seq.',
  grain [presentation_id, slide_id],
  tags [pptx, text, index, search]
);

SELECT
  presentation_id,
  slide_id,
  COUNT(*) AS text_run_count,
  STRING_AGG(COALESCE(text, ''), ' ' ORDER BY text_run_id) AS concatenated_text,
  MAX(_seq) AS last_seq
FROM vertex_pptx_text_run
WHERE presentation_id IS NOT NULL
GROUP BY presentation_id, slide_id
