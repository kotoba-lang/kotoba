-- Vertex mangaka count: mangaka record counts per repo/collection/kind.
MODEL (
  name dev.mv_vertex_mangaka_count,
  kind FULL,
  dialect postgres,
  description 'Per (repo, collection, kind): mangaka record count from vertex_mangaka.',
  grain [repo, collection, kind],
  tags [mangaka, count, rollup]
);

SELECT
  COALESCE(repo, '') AS repo,
  COALESCE(collection, '') AS collection,
  COALESCE(kind, split_part(collection, '.', array_length(string_to_array(collection, '.'), 1)), '') AS kind,
  COUNT(*)::BIGINT AS cnt
FROM vertex_mangaka
GROUP BY 1, 2, 3
