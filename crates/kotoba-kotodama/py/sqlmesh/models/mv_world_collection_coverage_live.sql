-- SQLMesh model: mv_world_collection_coverage_live
-- Per-collection world coverage (ADR-2605080500).
--
-- Source of truth for the deployed RisingWave streaming MV.
-- Apply changes via: rw-health-gate.sh gate + psql DDL channel.
--
-- Lineage:
--   dim_world_domain_collection
--   mv_world_did_per_host
--   mv_world_record_per_host_collection
--   → mv_world_collection_coverage_live

MODEL (
  name dev.mv_world_collection_coverage_live,
  kind FULL,
  dialect postgres,
  description 'Per-collection world coverage rate. Joins domain config with live DID and record counts.',
  grain [domain, app_host, collection],
  tags [coverage, world, collection, materialized_view]
);

SELECT
  d.domain,
  d.app_host,
  d.collection,
  d.world_total,
  d.unit,
  d.sector,
  CAST(COALESCE(wd.did_count,   0) AS BIGINT) AS did_count,
  CAST(COALESCE(rc.record_count, 0) AS BIGINT) AS record_count,
  CAST(
    GREATEST(COALESCE(wd.did_count, 0), COALESCE(rc.record_count, 0))
    AS BIGINT
  )                                            AS collected,
  CASE
    WHEN d.world_total > 0
    THEN (
      CAST(GREATEST(COALESCE(wd.did_count, 0), COALESCE(rc.record_count, 0)) AS DOUBLE)
      / CAST(d.world_total AS DOUBLE)
    )
    ELSE 0.0
  END                                          AS coverage_rate
FROM dim_world_domain_collection AS d
LEFT JOIN mv_world_did_per_host AS wd
  ON wd.app_host = d.app_host
LEFT JOIN mv_world_record_per_host_collection AS rc
  ON rc.app_host = d.app_host
  AND rc.collection = d.collection
