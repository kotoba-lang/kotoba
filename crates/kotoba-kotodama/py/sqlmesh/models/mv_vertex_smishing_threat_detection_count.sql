-- Vertex smishing threat detection count: per-(actor, classification) detection count.
MODEL (
  name dev.mv_vertex_smishing_threat_detection_count,
  kind FULL,
  dialect postgres,
  description 'Per (actor_id, classification): smishing threat detection count.',
  grain [actor_id, classification],
  tags [smishing, threat, detection, count]
);

SELECT
  actor_id,
  classification,
  COUNT(*)::BIGINT AS cnt
FROM vertex_smishing_threat_detection
GROUP BY actor_id, classification
