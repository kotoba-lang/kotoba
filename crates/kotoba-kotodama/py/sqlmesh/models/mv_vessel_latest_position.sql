-- Latest AIS position per MMSI vessel using MAX(ts_ms) + JOIN pattern.
-- DISTINCT ON is unsupported in RisingWave (ADR-2604241342).
MODEL (
  name dev.mv_vessel_latest_position,
  kind FULL,
  dialect postgres,
  description 'Latest AIS position per MMSI: most recent ts_ms row from vertex_vessel_position.',
  grain [mmsi],
  tags [ais, maritime, vessel, position]
);

SELECT
  p.mmsi,
  p.ts_ms,
  p.lat,
  p.lon,
  p.sog_knot,
  p.cog_deg,
  p.heading_deg,
  p.nav_status,
  p.source
FROM vertex_vessel_position p
JOIN (
  SELECT mmsi, MAX(ts_ms) AS max_ts_ms
  FROM vertex_vessel_position
  GROUP BY mmsi
) m ON p.mmsi = m.mmsi AND p.ts_ms = m.max_ts_ms
