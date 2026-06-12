-- ERC-725 AT resolution: active DID linkages between ERC-725 and AT Protocol.
MODEL (
  name dev.mv_erc725_at_resolution,
  kind FULL,
  dialect postgres,
  description 'Active (at_did, actor_did) pairs from vertex_erc725_linked_method where not revoked.',
  grain [at_did],
  tags [erc725, did, resolution, identity]
);

SELECT
  at_did,
  actor_did
FROM vertex_erc725_linked_method
WHERE at_did IS NOT NULL
  AND revoked_at IS NULL
