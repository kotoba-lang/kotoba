-- Data center dependency domain summary: node count and criticality per (actor, domain).
MODEL (
  name dev.mv_data_center_dependency_domain_summary,
  kind FULL,
  dialect postgres,
  description 'Per (actor_did, dependency_domain): node count, min/max level, and high/medium critical edge counts.',
  grain [actor_did, dependency_domain],
  tags [data_center, dependency, domain, criticality, summary]
);

SELECT
  v.actor_did,
  v.dependency_domain,
  COUNT(*) AS node_count,
  MIN(v.dependency_level) AS min_level,
  MAX(v.dependency_level) AS max_level,
  SUM(CASE WHEN e.criticality = 'high' THEN 1 ELSE 0 END) AS high_critical_edges,
  SUM(CASE WHEN e.criticality = 'medium' THEN 1 ELSE 0 END) AS medium_critical_edges
FROM vertex_data_center_dependency v
LEFT JOIN edge_data_center_dependency e ON e.dst_vid = v.vertex_id
GROUP BY v.actor_did, v.dependency_domain
