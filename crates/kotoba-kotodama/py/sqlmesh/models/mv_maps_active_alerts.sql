-- Maps active alerts: most recent service alert per (feed_id, alert_id), DISTINCT ON rewritten for RisingWave.
MODEL (
  name dev.mv_maps_active_alerts,
  kind FULL,
  dialect postgres,
  description 'Per (feed_id, alert_id): latest active service alert in last 24h via GROUP BY + JOIN on max(ts).',
  grain [feed_id, alert_id],
  tags [maps, alert, active]
);

SELECT
  a.feed_id,
  a.alert_id,
  a.ts,
  a.cause,
  a.effect,
  a.severity,
  a.header_text,
  a.description,
  a.url,
  a.active_from,
  a.active_until,
  a.affected_route_ids,
  a.affected_stop_ids,
  a.affected_trip_ids
FROM vertex_maps_service_alert a
JOIN (
  SELECT feed_id, alert_id, MAX(ts) AS max_ts
  FROM vertex_maps_service_alert
  WHERE (active_until IS NULL OR active_until > now())
    AND ts > now() - INTERVAL '24 hours'
  GROUP BY feed_id, alert_id
) latest
  ON latest.feed_id = a.feed_id
  AND latest.alert_id = a.alert_id
  AND latest.max_ts = a.ts
