-- Data center dependency global actor: per-country copy of dependency nodes.
MODEL (
  name dev.mv_data_center_dependency_global_actor,
  kind FULL,
  dialect postgres,
  description 'Per-country dependency node view from vertex_data_center_dependency_global with topology rank and domain coverage rate.',
  grain [vertex_id],
  tags [data_center, dependency, global, country, topology]
);

SELECT
  vertex_id AS dependency_vertex_id,
  actor_did,
  country_code,
  country_name,
  dependency_key,
  display_name,
  dependency_domain,
  dependency_level,
  in_degree,
  out_degree,
  reverse_topology_rank,
  domain_coverage_rate,
  domain_world_total
FROM vertex_data_center_dependency_global
