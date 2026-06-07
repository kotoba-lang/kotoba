-- Maps recent trip update: latest GTFS-RT trip update per (feed, trip, stop), DISTINCT ON rewritten.
MODEL (
  name dev.mv_maps_recent_trip_update,
  kind FULL,
  dialect postgres,
  description 'Per (feed_id, trip_id, stop_sequence): latest trip update in last 30min via GROUP BY + JOIN.',
  grain [feed_id, trip_id, stop_sequence],
  tags [maps, gtfs, trip_update, realtime]
);

SELECT
  t.feed_id,
  t.trip_id,
  t.stop_sequence,
  t.stop_id,
  t.route_id,
  t.ts,
  t.schedule_relationship,
  t.arrival_delay_sec,
  t.departure_delay_sec,
  t.arrival_time,
  t.departure_time,
  t.uncertainty_sec
FROM vertex_maps_trip_update t
JOIN (
  SELECT feed_id, trip_id, stop_sequence, MAX(ts) AS max_ts
  FROM vertex_maps_trip_update
  WHERE ts > now() - INTERVAL '30 minutes'
  GROUP BY feed_id, trip_id, stop_sequence
) latest
  ON latest.feed_id = t.feed_id
  AND latest.trip_id = t.trip_id
  AND latest.stop_sequence = t.stop_sequence
  AND latest.max_ts = t.ts
