-- Critical path: infra capabilities with most dependent actions and blocked counts.
MODEL (
  name dev.mv_critical_path,
  kind FULL,
  dialect postgres,
  description 'Infra capabilities with dependent actions, blocked count, and max topo level (bottleneck detection).',
  grain [vertex_id],
  tags [strategy, critical_path, infra, bottleneck, blocked]
);

SELECT
  i.vertex_id,
  i.capability_code,
  i.display_name,
  i.status,
  COUNT(DISTINCT e.src_vid) AS dependent_actions,
  COUNT(DISTINCT a.vertex_id) FILTER (WHERE a.status = 'blocked') AS blocked_count,
  MAX(a.topo_level) AS max_topo_level
FROM vertex_infra_capability i
LEFT JOIN edge_enables e ON e.src_vid = i.vertex_id
LEFT JOIN vertex_action a ON a.vertex_id = e.dst_vid
GROUP BY i.vertex_id, i.capability_code, i.display_name, i.status
HAVING COUNT(DISTINCT e.src_vid) > 0
