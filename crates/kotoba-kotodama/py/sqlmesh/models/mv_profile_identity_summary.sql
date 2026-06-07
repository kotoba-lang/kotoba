-- Profile identity summary: aggregate profile linkage stats.
MODEL (
  name dev.mv_profile_identity_summary,
  kind FULL,
  dialect postgres,
  description 'Aggregate counts: total profiles, linked actor/did profiles, fully linked profiles.',
  grain [],
  tags [profile, identity, summary]
);

SELECT
  COUNT(*)::BIGINT AS total_profiles,
  SUM(CASE WHEN actor_vertex_id IS NOT NULL THEN 1 ELSE 0 END)::BIGINT AS linked_actor_profiles,
  SUM(CASE WHEN did_vertex_id IS NOT NULL THEN 1 ELSE 0 END)::BIGINT AS linked_did_profiles,
  SUM(CASE WHEN actor_vertex_id IS NOT NULL AND did_vertex_id IS NOT NULL THEN 1 ELSE 0 END)::BIGINT AS fully_linked_profiles
FROM dev.mv_profile_identity_topology
