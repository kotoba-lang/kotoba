-- Vertex livecam detection event count: per-(actor, camera) detection event count.
MODEL (
  name dev.mv_vertex_livecam_detection_event_count,
  kind FULL,
  dialect postgres,
  description 'Per (actor_id, camera_slug): detection event count from vertex_livecam_detection_event.',
  grain [actor_id, camera_slug],
  tags [livecam, detection, count]
);

SELECT
  actor_id,
  camera_slug,
  COUNT(*)::BIGINT AS cnt
FROM vertex_livecam_detection_event
GROUP BY actor_id, camera_slug
