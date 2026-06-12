-- OS agent state: per-agent state with latest event timestamp.
MODEL (
  name dev.mv_os_agent_state,
  kind FULL,
  dialect postgres,
  description 'Per agent: state from vertex_os_agent + latest event_at fallback to updated_at.',
  grain [agent_id],
  tags [os, agent, state]
);

SELECT
  a.agent_id,
  a.did,
  a.app_id,
  a.name,
  a.status AS state,
  a.created_at,
  COALESCE(e.latest_event_at, a.updated_at) AS updated_at
FROM vertex_os_agent a
LEFT JOIN (
  SELECT agent_id, MAX(created_at) AS latest_event_at
  FROM vertex_os_agent_event
  GROUP BY agent_id
) e ON a.agent_id = e.agent_id
