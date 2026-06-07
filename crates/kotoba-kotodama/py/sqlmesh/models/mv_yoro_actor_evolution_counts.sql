-- Yoro actor evolution counts: per-actor counts of kyumei/shinka/hinshitsu/knowledge events.
MODEL (
  name dev.mv_yoro_actor_evolution_counts,
  kind FULL,
  dialect postgres,
  description 'Per actor_did: counts of kyumei/shinka/hinshitsu/knowledge events via UNION ALL.',
  grain [actor_did],
  tags [yoro, actor, evolution, counts]
);

SELECT
  actor_did,
  COUNT(*) FILTER (WHERE kind = 'kyumei') AS kyumei_count,
  COUNT(*) FILTER (WHERE kind = 'shinka') AS shinka_count,
  COUNT(*) FILTER (WHERE kind = 'hinshitsu') AS hinshitsu_count,
  COUNT(*) FILTER (WHERE kind = 'knowledge') AS knowledge_count
FROM (
  SELECT actor_did, 'kyumei' AS kind FROM vertex_yoro_kyumei_validation
  UNION ALL SELECT actor_did, 'shinka' AS kind FROM vertex_yoro_shinka_evolution
  UNION ALL SELECT actor_did, 'hinshitsu' AS kind FROM vertex_yoro_hinshitsu_assessment
  UNION ALL SELECT actor_did, 'knowledge' AS kind FROM vertex_yoro_shinka_knowledge
) events
GROUP BY actor_did
