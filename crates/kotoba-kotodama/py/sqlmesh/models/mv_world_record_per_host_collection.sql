-- World record per host collection: per-(canonicalized host, collection) repo record count.
MODEL (
  name dev.mv_world_record_per_host_collection,
  kind FULL,
  dialect postgres,
  description 'Per (canonical app_host, collection): repo record count from vertex_repo_record.',
  grain [app_host, collection],
  tags [world, record, host, collection, coverage]
);

WITH normalized AS (
  SELECT
    COALESCE(a.canonical_host, split_part(split_part(r.repo, 'did:web:', 2), '.', 1)) AS app_host,
    r.collection AS collection
  FROM vertex_repo_record r
  LEFT JOIN dim_app_host_alias a
    ON split_part(split_part(r.repo, 'did:web:', 2), '.', 1) = a.alias_host
)
SELECT
  app_host,
  collection,
  COUNT(*)::BIGINT AS record_count
FROM normalized
GROUP BY app_host, collection
