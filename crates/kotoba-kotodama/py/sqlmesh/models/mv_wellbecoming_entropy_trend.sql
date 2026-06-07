-- ADR-2604291800 Well-Becoming: hourly Shannon η proxy via separation_delta trend.
-- avg_separation_delta → 0 indicates degrading social connections (η drop).
MODEL (
  name dev.mv_wellbecoming_entropy_trend,
  kind FULL,
  dialect postgres,
  description 'Hourly Well-Becoming entropy trend: avg_separation_delta + floor violations per hour.',
  grain [hour],
  tags [wellbecoming, entropy, shannon_eta, adr_2604291800]
);

SELECT
  date_trunc('hour', created_at)                                  AS hour,
  AVG(separation_delta) FILTER (WHERE separation_delta IS NOT NULL) AS avg_separation_delta,
  COUNT(*)                                                         AS event_count,
  COUNT(DISTINCT case_id)                                          AS active_conversations,
  SUM(CASE WHEN floor_violated = true THEN 1 ELSE 0 END)          AS floor_violations,
  AVG(score_total) FILTER (WHERE scored = true)                    AS avg_score_total
FROM vertex_wellbecoming_event
GROUP BY date_trunc('hour', created_at)
