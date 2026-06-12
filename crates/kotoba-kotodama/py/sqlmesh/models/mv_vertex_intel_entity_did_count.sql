-- Vertex intel entity DID count: per-actor intel entity count.
MODEL (
  name dev.mv_vertex_intel_entity_did_count,
  kind FULL,
  dialect postgres,
  description 'Per actor_id: intel entity DID count from vertex_intel_entity_did.',
  grain [actor_id],
  tags [intel, entity, did, count]
);

SELECT
  actor_id,
  COUNT(*)::BIGINT AS cnt
FROM vertex_intel_entity_did
GROUP BY actor_id
