-- Vertex tenso transfer request count: per-(actor, status) transfer request count.
MODEL (
  name dev.mv_vertex_tenso_transfer_request_count,
  kind FULL,
  dialect postgres,
  description 'Per (actor_id, status): tenso transfer request count.',
  grain [actor_id, status],
  tags [tenso, transfer_request, count]
);

SELECT
  actor_id,
  status,
  COUNT(*)::BIGINT AS cnt
FROM vertex_tenso_transfer_request
GROUP BY actor_id, status
