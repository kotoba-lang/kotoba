-- Vertex yotei event count: per-(actor, calendar, status) event count.
MODEL (
  name dev.mv_vertex_yotei_event_count,
  kind FULL,
  dialect postgres,
  description 'Per (actor_id, calendar_id, status): event count.',
  grain [actor_id, calendar_id, status],
  tags [yotei, event, count]
);

SELECT
  actor_id,
  calendar_id,
  status,
  COUNT(*)::BIGINT AS cnt
FROM vertex_yotei_event
GROUP BY actor_id, calendar_id, status
