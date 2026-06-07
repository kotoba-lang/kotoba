-- Lifehack static risk now: per-H3-cell humidity-based dust risk readings.
MODEL (
  name dev.mv_lifehack_static_risk_now,
  kind FULL,
  dialect postgres,
  description 'Per location_h3: reading count, avg/min humidity, latest ts when humidity below 40%.',
  grain [location_h3],
  tags [lifehack, environment, risk, h3]
);

SELECT
  location_h3,
  COUNT(*) AS reading_count,
  AVG(humidity_pct) AS avg_humidity_pct,
  MIN(humidity_pct) AS min_humidity_pct,
  MAX(ts_ms) AS last_ts_ms
FROM vertex_lifehack_environment_reading
WHERE status = 'active'
  AND humidity_pct IS NOT NULL
  AND humidity_pct < 40.0
GROUP BY location_h3
