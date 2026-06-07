-- Airborne aircraft count per origin country (5-minute window).
MODEL (
  name dev.mv_aircraft_country_count,
  kind FULL,
  dialect postgres,
  description 'Count of airborne aircraft per origin_country within the last 5 minutes.',
  grain [origin_country],
  tags [aircraft, aviation, live, maps, count]
);

SELECT
  origin_country,
  COUNT(*) AS airborne_count
FROM vertex_aircraft_state
WHERE on_ground = false
  AND to_timestamp(ts_ms / 1000.0) > now() - INTERVAL '5 minutes'
GROUP BY origin_country
