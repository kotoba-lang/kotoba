-- Vertex yotei booking count: per-(actor, calendar, status) booking count.
MODEL (
  name dev.mv_vertex_yotei_booking_count,
  kind FULL,
  dialect postgres,
  description 'Per (actor_id, calendar_id, status): booking count.',
  grain [actor_id, calendar_id, status],
  tags [yotei, booking, count]
);

SELECT
  actor_id,
  calendar_id,
  status,
  COUNT(*)::BIGINT AS cnt
FROM vertex_yotei_booking
GROUP BY actor_id, calendar_id, status
