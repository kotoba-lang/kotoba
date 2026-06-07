-- ADR-2604291800 Well-Becoming: per-agent rolling score aggregates.
MODEL (
  name dev.mv_wellbecoming_score_actor,
  kind FULL,
  dialect postgres,
  description 'Per-agent Well-Becoming rolling scores and floor violation count.',
  grain [agent_did],
  tags [wellbecoming, score, adr_2604291800]
);

SELECT
  agent_did,
  COUNT(*)                                                       AS event_count,
  AVG(score_spirit)       FILTER (WHERE scored = true)           AS avg_spirit,
  AVG(score_wellbecoming) FILTER (WHERE scored = true)           AS avg_wellbecoming,
  AVG(score_feeling)      FILTER (WHERE scored = true)           AS avg_feeling,
  AVG(score_buffer)       FILTER (WHERE scored = true)           AS avg_buffer,
  AVG(score_total)        FILTER (WHERE scored = true)           AS avg_total,
  SUM(CASE WHEN floor_violated = true THEN 1 ELSE 0 END)         AS floor_violations,
  AVG(separation_delta)   FILTER (WHERE separation_delta IS NOT NULL) AS avg_separation_delta,
  MAX(created_at)                                                AS last_activity_at
FROM vertex_wellbecoming_event
GROUP BY agent_did
