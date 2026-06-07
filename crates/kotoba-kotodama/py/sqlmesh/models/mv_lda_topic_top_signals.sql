-- LDA topic top signals: signal count and total weight per topic.
MODEL (
  name dev.mv_lda_topic_top_signals,
  kind FULL,
  dialect postgres,
  description 'Per topic: entity kind hint, coherence score, distinct signal count, and total weight.',
  grain [topic_vid],
  tags [lda, topic, signal]
);

SELECT
  e.src_vid AS topic_vid,
  t.entity_kind_hint,
  t.coherence_score,
  COUNT(DISTINCT e.dst_vid) AS signal_count,
  SUM(e.weight) AS total_weight
FROM edge_topic_signal_weight e
JOIN vertex_lda_topic t ON t.vertex_id = e.src_vid
GROUP BY e.src_vid, t.entity_kind_hint, t.coherence_score
