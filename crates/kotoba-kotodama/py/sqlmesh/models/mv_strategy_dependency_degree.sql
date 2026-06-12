-- Strategy dependency degree: per-vertex dependency in/out counts via strategy contract view.
MODEL (
  name dev.mv_strategy_dependency_degree,
  kind FULL,
  dialect postgres,
  description 'Per strategy vertex: dependency_count (outbound) and dependent_count (inbound) with declared topo level.',
  grain [graph_scope, vertex_id],
  tags [strategy, dependency, degree, topology]
);

WITH edges AS (
  SELECT dependent_vid, prerequisite_vid
  FROM view_strategy_dependency_edge_contract
),
nodes AS (
  SELECT vertex_id FROM view_strategy_dependency_known_vertex
  UNION
  SELECT dependent_vid AS vertex_id FROM edges
  UNION
  SELECT prerequisite_vid AS vertex_id FROM edges
),
dep_counts AS (
  SELECT dependent_vid AS vertex_id, COUNT(*) AS dependency_count
  FROM edges
  GROUP BY dependent_vid
),
dependent_counts AS (
  SELECT prerequisite_vid AS vertex_id, COUNT(*) AS dependent_count
  FROM edges
  GROUP BY prerequisite_vid
)
SELECT
  'strategy' AS graph_scope,
  n.vertex_id,
  kv.vertex_kind,
  kv.display_name,
  kv.status,
  COALESCE(dc.dependency_count, 0) AS dependency_count,
  COALESCE(pc.dependent_count, 0) AS dependent_count,
  a.topo_level AS declared_topo_level,
  kv.owner_did,
  kv.sensitivity_ord
FROM nodes n
LEFT JOIN view_strategy_dependency_known_vertex kv ON kv.vertex_id = n.vertex_id
LEFT JOIN vertex_action a ON a.vertex_id = n.vertex_id
LEFT JOIN dep_counts dc ON dc.vertex_id = n.vertex_id
LEFT JOIN dependent_counts pc ON pc.vertex_id = n.vertex_id
