-- Vertex spatial count: per-(label, collection) spatial entity count.
MODEL (
  name dev.mv_vertex_spatial_count,
  kind FULL,
  dialect postgres,
  description 'Per (label, collection): spatial vertex count.',
  grain [label, collection],
  tags [spatial, count, rollup]
);

SELECT
  COALESCE(label, '') AS label,
  COALESCE(collection, '') AS collection,
  COUNT(*)::BIGINT AS cnt
FROM vertex_spatial
GROUP BY 1, 2
