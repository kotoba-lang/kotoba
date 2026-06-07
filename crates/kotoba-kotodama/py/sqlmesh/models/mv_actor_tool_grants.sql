-- Actor tool grant projection — primary path for tools/list + tools/call auth.
-- Source: vertex_capability (toolGrant + tool joins).
MODEL (
  name dev.mv_actor_tool_grants,
  kind FULL,
  dialect postgres,
  description 'Per-actor active tool grants joined to tool registry (capability_worker).',
  grain [actor_did, tool_name],
  tags [actor, tools, capability]
);

SELECT
  COALESCE(NULLIF(g.did, ''), g.repo) AS actor_did,
  g.name                              AS tool_name,
  CAST(g.created_date AS VARCHAR)     AS granted_at,
  t.vertex_id                         AS tool_vertex_id,
  t.capability_worker                 AS capability_worker
FROM vertex_capability g
JOIN vertex_capability t
  ON t.name = g.name
 AND t.collection = 'com.etzhayyim.tool.tool'
 AND t.status = 'active'
WHERE g.collection = 'com.etzhayyim.actor.toolGrant'
  AND g.status = 'active'
