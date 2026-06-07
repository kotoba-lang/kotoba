-- Profile identity topology: per-profile linkage to vertex_actor and vertex_did.
MODEL (
  name dev.mv_profile_identity_topology,
  kind FULL,
  dialect postgres,
  description 'Per profile: actor_vertex_id and did_vertex_id via DID match (LEFT JOIN).',
  grain [profile_vertex_id],
  tags [profile, identity, topology]
);

SELECT
  p.vertex_id AS profile_vertex_id,
  p.did,
  p.repo,
  p.handle,
  a.vertex_id AS actor_vertex_id,
  d.vertex_id AS did_vertex_id
FROM vertex_profile p
LEFT JOIN vertex_actor a ON a.did = p.did
LEFT JOIN vertex_did d ON d.did = p.did
