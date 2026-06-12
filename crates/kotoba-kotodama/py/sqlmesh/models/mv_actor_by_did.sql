-- Actor reverse lookup by DID.
MODEL (
  name dev.mv_actor_by_did,
  kind FULL,
  dialect postgres,
  description 'Actor reverse lookup by DID from vertex_actor.',
  grain [did],
  tags [actor, identity, did]
);

SELECT did, vertex_id, handle, display_name, avatar_cid, status
FROM vertex_actor
