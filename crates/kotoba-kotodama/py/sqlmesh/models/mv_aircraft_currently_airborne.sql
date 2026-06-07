-- Live airborne aircraft: not on ground, position fresher than 90 seconds.
MODEL (
  name dev.mv_aircraft_currently_airborne,
  kind FULL,
  dialect postgres,
  description 'Currently-airborne aircraft from vertex_aircraft_state with ts_ms within 90s.',
  grain [icao24],
  tags [aircraft, aviation, live, ais, maps]
);

SELECT
  icao24,
  callsign,
  lat,
  lon,
  baro_altitude_m,
  velocity_ms,
  heading_deg,
  vertical_rate_ms,
  origin_country,
  source,
  ts_ms
FROM vertex_aircraft_state
WHERE on_ground = false
  AND to_timestamp(ts_ms / 1000.0) > now() - INTERVAL '90 seconds'
