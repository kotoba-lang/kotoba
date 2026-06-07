-- Satellite visible now: passes whose AOS-LOS window contains the current time.
MODEL (
  name dev.mv_satellite_visible_now,
  kind FULL,
  dialect postgres,
  description 'Per (norad_id, observer_h3): visible satellite passes with AOS-LOS window covering now().',
  grain [norad_id, observer_h3, aos_ms],
  tags [satellite, pass, visible, realtime]
);

SELECT
  norad_id,
  observer_h3,
  observer_lat,
  observer_lon,
  aos_ms,
  los_ms,
  max_elevation_deg,
  peak_azimuth_deg,
  visible_at_night,
  magnitude
FROM vertex_satellite_pass
WHERE to_timestamp(aos_ms / 1000.0) <= now() + INTERVAL '0 seconds'
  AND to_timestamp(los_ms / 1000.0) >= now() - INTERVAL '0 seconds'
