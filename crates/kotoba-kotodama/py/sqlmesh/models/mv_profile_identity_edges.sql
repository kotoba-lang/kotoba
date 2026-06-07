-- Profile identity edges: synthetic edges from profile to DID/actor vertices.
MODEL (
  name dev.mv_profile_identity_edges,
  kind FULL,
  dialect postgres,
  description 'Synthetic profile_to_did and profile_to_actor edges via DID match.',
  grain [edge_id],
  tags [profile, identity, edge]
);

SELECT
  CONCAT('profile-to-did:', p.vertex_id, ':', d.vertex_id) AS edge_id,
  p.vertex_id AS src_vid,
  d.vertex_id AS dst_vid,
  'profile_to_did'::VARCHAR AS edge_kind
FROM vertex_profile p
JOIN vertex_did d ON d.did = p.did
UNION ALL
SELECT
  CONCAT('profile-to-actor:', p.vertex_id, ':', a.vertex_id) AS edge_id,
  p.vertex_id AS src_vid,
  a.vertex_id AS dst_vid,
  'profile_to_actor'::VARCHAR AS edge_kind
FROM vertex_profile p
JOIN vertex_actor a ON a.did = p.did
