-- Vertex crypto asset freeze incident count: per-(actor, freeze_status) incident count.
MODEL (
  name dev.mv_vertex_crypto_asset_freeze_incident_count,
  kind FULL,
  dialect postgres,
  description 'Per (actor_id, freeze_status): incident count from vertex_crypto_asset_freeze_incident.',
  grain [actor_id, freeze_status],
  tags [crypto, freeze, incident, count]
);

SELECT
  actor_id,
  freeze_status,
  COUNT(*)::BIGINT AS cnt
FROM vertex_crypto_asset_freeze_incident
GROUP BY actor_id, freeze_status
