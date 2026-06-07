-- Vertex IP address total: aggregate IP address count.
MODEL (
  name dev.mv_vertex_ip_address_total,
  kind FULL,
  dialect postgres,
  description 'Total count from vertex_ip_address.',
  grain [],
  tags [ip_address, count, total]
);

SELECT COUNT(*)::BIGINT AS cnt
FROM vertex_ip_address
