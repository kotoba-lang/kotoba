-- Vertex livecam anomaly count: per-(actor, zone, severity) anomaly count.
MODEL (
  name dev.mv_vertex_livecam_anomaly_count,
  kind FULL,
  dialect postgres,
  description 'Per (actor_id, zone_slug, severity): anomaly count from vertex_livecam_anomaly.',
  grain [actor_id, zone_slug, severity],
  tags [livecam, anomaly, count]
);

SELECT
  actor_id,
  zone_slug,
  severity,
  COUNT(*)::BIGINT AS cnt
FROM vertex_livecam_anomaly
GROUP BY actor_id, zone_slug, severity
