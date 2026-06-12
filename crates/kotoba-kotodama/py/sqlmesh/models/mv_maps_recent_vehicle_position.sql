-- Maps recent vehicle position: latest GTFS-RT vehicle position per (feed, vehicle), DISTINCT ON rewritten.
MODEL (
  name dev.mv_maps_recent_vehicle_position,
  kind FULL,
  dialect postgres,
  description 'Per (feed_id, vehicle_id): latest vehicle position in last 5min via GROUP BY + JOIN.',
  grain [feed_id, vehicle_id],
  tags [maps, gtfs, vehicle_position, realtime]
);

SELECT
  v.feed_id,
  v.vehicle_id,
  v.ts,
  v.trip_id,
  v.route_id,
  v.stop_id,
  v.lat,
  v.lng,
  v.bearing,
  v.speed_mps,
  v.occupancy_status,
  v.current_status,
  v.congestion_level,
  v.label
FROM vertex_maps_vehicle_position v
JOIN (
  SELECT feed_id, vehicle_id, MAX(ts) AS max_ts
  FROM vertex_maps_vehicle_position
  WHERE ts > now() - INTERVAL '5 minutes'
  GROUP BY feed_id, vehicle_id
) latest
  ON latest.feed_id = v.feed_id
  AND latest.vehicle_id = v.vehicle_id
  AND latest.max_ts = v.ts
