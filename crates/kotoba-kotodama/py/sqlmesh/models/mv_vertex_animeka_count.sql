-- Vertex animeka count: animeka record counts per repo/collection/kind.
MODEL (
  name dev.mv_vertex_animeka_count,
  kind FULL,
  dialect postgres,
  description 'Per (repo, collection, kind): animeka record count from vertex_animeka.',
  grain [repo, collection, kind],
  tags [animeka, count, rollup]
);

SELECT
  COALESCE(repo, '') AS repo,
  COALESCE(collection, '') AS collection,
  COALESCE(kind, split_part(collection, '.', array_length(string_to_array(collection, '.'), 1)), '') AS kind,
  COUNT(*)::BIGINT AS cnt
FROM vertex_animeka
GROUP BY 1, 2, 3
