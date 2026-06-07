-- Data center dependency reverse topology: in/out degree and topology rank per dependency node.
MODEL (
  name dev.mv_data_center_dependency_reverse_topology,
  kind FULL,
  dialect postgres,
  description 'Per dependency node: in-degree, out-degree, and reverse_topology_rank (dependency_level*100 + in_degree).',
  grain [vertex_id],
  tags [data_center, dependency, topology, in_degree, out_degree, criticality]
);

WITH in_deg AS (
  SELECT dst_vid, COUNT(*) AS in_degree
  FROM edge_data_center_dependency
  GROUP BY dst_vid
),
out_deg AS (
  SELECT src_vid, COUNT(*) AS out_degree
  FROM edge_data_center_dependency
  GROUP BY src_vid
)
SELECT
  v.vertex_id,
  v.actor_did,
  v.dependency_key,
  v.display_name,
  v.dependency_domain,
  v.dependency_level,
  COALESCE(i.in_degree, 0) AS in_degree,
  COALESCE(o.out_degree, 0) AS out_degree,
  (v.dependency_level * 100 + COALESCE(i.in_degree, 0)) AS reverse_topology_rank,
  v.status,
  v.updated_at
FROM vertex_data_center_dependency v
LEFT JOIN in_deg i ON i.dst_vid = v.vertex_id
LEFT JOIN out_deg o ON o.src_vid = v.vertex_id
