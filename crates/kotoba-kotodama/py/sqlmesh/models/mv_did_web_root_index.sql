-- DID web root index: sub-DID to root-DID mapping for did:web entries.
MODEL (
  name dev.mv_did_web_root_index,
  kind FULL,
  dialect postgres,
  description 'Distinct mapping of did:web sub-DIDs to their 3-segment root DID (did:web:host).',
  grain [sub_did],
  tags [did, identity, did_web, root, index]
);

SELECT DISTINCT
  did AS sub_did,
  split_part(did, ':', 1) || ':' || split_part(did, ':', 2) || ':' || split_part(did, ':', 3) AS root_did
FROM vertex_did
WHERE did LIKE 'did:web:%'
