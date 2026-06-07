-- Lifehack top tips by topic: active tips with effectiveness scores.
MODEL (
  name dev.mv_lifehack_top_tips_by_topic,
  kind FULL,
  dialect postgres,
  description 'Active lifehack tips with effectiveness_score, body, cost, difficulty, and authority.',
  grain [tip_id],
  tags [lifehack, tip, topic, effectiveness]
);

SELECT
  t.topic_id,
  t.tip_id,
  t.body_ja,
  t.effectiveness_score,
  t.cost_jpy_min,
  t.difficulty,
  t.source_authority
FROM vertex_lifehack_tip t
WHERE t.status = 'active'
  AND t.effectiveness_score IS NOT NULL
