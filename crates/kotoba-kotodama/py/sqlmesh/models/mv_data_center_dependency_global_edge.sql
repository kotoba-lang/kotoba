-- Data center dependency global edge: flat projection of cross-actor data center dependency edges.
MODEL (
  name dev.mv_data_center_dependency_global_edge,
  kind FULL,
  dialect postgres,
  description 'Flat projection of edge_data_center_dependency_global: actor, country, src/dst vertex, edge kind, criticality.',
  grain [edge_id],
  tags [data_center, dependency, edge, global]
);

SELECT
  edge_id,
  actor_did,
  country_code,
  country_name,
  src_vertex_id,
  dst_vertex_id,
  from_node_key,
  to_node_key,
  edge_kind,
  criticality,
  path_weight,
  status,
  collected_at
FROM edge_data_center_dependency_global
