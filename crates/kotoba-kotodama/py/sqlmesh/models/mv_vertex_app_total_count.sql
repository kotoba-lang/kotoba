-- Vertex app total count: aggregate app count where DID is non-null.
MODEL (
  name dev.mv_vertex_app_total_count,
  kind FULL,
  dialect postgres,
  description 'Total count from vertex_app where did IS NOT NULL.',
  grain [],
  tags [app, count, total]
);

SELECT COUNT(*)::BIGINT AS cnt
FROM vertex_app
WHERE did IS NOT NULL
