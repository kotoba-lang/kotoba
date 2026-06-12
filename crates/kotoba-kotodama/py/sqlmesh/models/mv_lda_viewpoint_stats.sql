-- LDA viewpoint stats: signal and topic counts per viewpoint.
MODEL (
  name dev.mv_lda_viewpoint_stats,
  kind FULL,
  dialect postgres,
  description 'Per (viewpoint_vid, viewpoint_kind): distinct signal count, topic count, and entity count.',
  grain [viewpoint_vid],
  tags [lda, viewpoint, stats]
);

SELECT
  vp.vertex_id AS viewpoint_vid,
  vp.viewpoint_kind,
  COUNT(DISTINCT s.vertex_id) AS signal_count,
  COUNT(DISTINCT t.vertex_id) AS topic_count,
  0 AS entity_count
FROM vertex_lda_viewpoint vp
LEFT JOIN vertex_lda_signal s ON s.viewpoint_vid = vp.vertex_id
LEFT JOIN vertex_lda_topic t ON t.primary_viewpoint_vid = vp.vertex_id
GROUP BY vp.vertex_id, vp.viewpoint_kind
