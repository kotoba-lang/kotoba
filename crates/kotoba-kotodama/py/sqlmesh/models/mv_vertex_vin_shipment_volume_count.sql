-- Vertex VIN shipment volume count: per-(actor, year, jurisdiction, vehicle_type) shipment volume.
MODEL (
  name dev.mv_vertex_vin_shipment_volume_count,
  kind FULL,
  dialect postgres,
  description 'Per (actor_id, year, jurisdiction, vehicle_type): row count and total volume.',
  grain [actor_id, year, jurisdiction, vehicle_type],
  tags [vin, shipment, volume, count]
);

SELECT
  actor_id,
  year,
  jurisdiction,
  vehicle_type,
  COUNT(*)::BIGINT AS cnt,
  SUM(volume)::BIGINT AS total_volume
FROM vertex_vin_shipment_volume
GROUP BY actor_id, year, jurisdiction, vehicle_type
