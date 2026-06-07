-- Vessel density grid at 0.1° lat/lon resolution in 15-min time buckets.
-- Phase 1 coarse grid; Phase 2 will swap cell_id to H3 res-6 via UDF.
MODEL (
  name dev.mv_vessel_density_grid,
  kind FULL,
  dialect postgres,
  description 'AIS vessel density per 0.1° grid cell × type_class × 15-min bucket.',
  grain [cell_id, type_class, bucket_ms],
  tags [ais, maritime, vessel, density, grid]
);

SELECT
  ('lat:' || (FLOOR(p.lat * 10)::int)::varchar
   || '|lon:' || (FLOOR(p.lon * 10)::int)::varchar) AS cell_id,
  FLOOR(p.lat * 10) / 10.0                          AS lat_bin,
  FLOOR(p.lon * 10) / 10.0                          AS lon_bin,
  vessel_type_class(v.type_code)                     AS type_class,
  (p.ts_ms / 900000) * 900000                        AS bucket_ms,
  COUNT(*)                                           AS hit_count,
  COUNT(DISTINCT p.mmsi)                             AS vessel_count
FROM vertex_vessel_position p
LEFT JOIN vertex_vessel v ON v.mmsi = p.mmsi
GROUP BY 1, 2, 3, 4, 5
