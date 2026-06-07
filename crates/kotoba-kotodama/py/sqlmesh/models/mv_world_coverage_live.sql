-- World coverage live: per-domain DID/record/vertex coverage rate against world_total.
MODEL (
  name dev.mv_world_coverage_live,
  kind FULL,
  dialect postgres,
  description 'Per (domain, app_host): world target totals vs collected DID/record/vertex counts and coverage_rate.',
  grain [domain, app_host],
  tags [world, coverage, live]
);

SELECT
  d.domain,
  d.app_host,
  d.world_total,
  d.unit,
  d.sector,
  COALESCE(p.did_count, 0) AS did_count,
  COALESCE(r.record_count, 0) AS record_count,
  COALESCE(v.vertex_count, 0) AS vertex_count,
  GREATEST(
    COALESCE(p.did_count, 0),
    COALESCE(r.record_count, 0),
    COALESCE(v.vertex_count, 0)
  ) AS collected,
  GREATEST(
    COALESCE(p.did_count, 0),
    COALESCE(r.record_count, 0),
    COALESCE(v.vertex_count, 0)
  )::DOUBLE PRECISION / NULLIF(d.world_total, 0) AS coverage_rate
FROM dim_world_domain d
LEFT JOIN dev.mv_world_did_per_host p ON p.app_host = d.app_host
LEFT JOIN dev.mv_world_record_per_host r ON r.app_host = d.app_host
LEFT JOIN mv_world_vertex_per_host v ON v.app_host = d.app_host
