-- Vertex VIN vehicle count: per-(actor, make) vehicle count.
MODEL (
  name dev.mv_vertex_vin_vehicle_count,
  kind FULL,
  dialect postgres,
  description 'Per (actor_id, make): VIN vehicle count.',
  grain [actor_id, make],
  tags [vin, vehicle, count]
);

SELECT
  actor_id,
  make,
  COUNT(*)::BIGINT AS cnt
FROM vertex_vin_vehicle
GROUP BY actor_id, make
