-- Governance policy projection per actor DID.
-- Source: edge_governance + vertex_governance join.
MODEL (
  name dev.mv_actor_governance_policy,
  kind FULL,
  dialect postgres,
  description 'Per-actor governance policy projection: policy_vid, policy_name, kind, standard.',
  grain [actor_did, policy_vid],
  tags [actor, governance, policy]
);

SELECT
  e.src_vid   AS actor_did,
  v.vertex_id AS policy_vid,
  v.name      AS policy_name,
  v.kind      AS kind,
  v.standard  AS standard
FROM edge_governance e
JOIN vertex_governance v ON v.vertex_id = e.dst_vid
