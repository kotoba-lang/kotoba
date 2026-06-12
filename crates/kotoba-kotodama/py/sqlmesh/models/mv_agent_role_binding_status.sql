-- Per-app agent role binding count and latest creation timestamp.
MODEL (
  name dev.mv_agent_role_binding_status,
  kind FULL,
  dialect postgres,
  description 'Count and latest created_at of agent role bindings grouped by app_id.',
  grain [app_id],
  tags [agent, role, binding, status]
);

SELECT app_id, COUNT(*) AS binding_count, MAX(created_at) AS latest_created_at
FROM vertex_agent_role_binding
GROUP BY app_id
