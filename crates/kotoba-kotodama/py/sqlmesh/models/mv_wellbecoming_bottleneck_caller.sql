-- ADR-2604291800 Well-Becoming: per-caller bottleneck summary for proactiveConnect gate.
MODEL (
  name dev.mv_wellbecoming_bottleneck_caller,
  kind FULL,
  dialect postgres,
  description 'Per-caller Well-Becoming event aggregates: avg scores, floor violations, separation delta.',
  grain [caller_did],
  tags [wellbecoming, bottleneck, adr_2604291800]
);

SELECT
  case_id                                                         AS caller_did,
  COUNT(*)                                                        AS event_count,
  AVG(score_spirit)       FILTER (WHERE scored = true)           AS avg_spirit,
  AVG(score_wellbecoming) FILTER (WHERE scored = true)           AS avg_wellbecoming,
  AVG(score_feeling)      FILTER (WHERE scored = true)           AS avg_feeling,
  AVG(score_buffer)       FILTER (WHERE scored = true)           AS avg_buffer,
  AVG(score_total)        FILTER (WHERE scored = true)           AS avg_total,
  AVG(separation_delta)   FILTER (WHERE separation_delta IS NOT NULL) AS avg_separation_delta,
  SUM(CASE WHEN floor_violated = true THEN 1 ELSE 0 END)         AS floor_violations,
  MAX(created_at)                                                 AS last_activity_at
FROM vertex_wellbecoming_event
GROUP BY case_id
