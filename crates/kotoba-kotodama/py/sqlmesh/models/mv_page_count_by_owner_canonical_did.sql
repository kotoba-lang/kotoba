-- Page count by owner canonical DID: page count per canonicalized actor DID.
MODEL (
  name dev.mv_page_count_by_owner_canonical_did,
  kind FULL,
  dialect postgres,
  description 'Per canonical_actor_did: page count, with site.etzhayyim.com sub-DID and did:web normalization.',
  grain [canonical_actor_did],
  tags [page, owner, canonical_did]
);

SELECT
  CASE
    WHEN owner_did LIKE 'did:web:site.etzhayyim.com:%'
      THEN CONCAT(
        'did:web:',
        SPLIT_PART(SPLIT_PART(owner_did, 'did:web:site.etzhayyim.com:', 2), ':', 1),
        '.etzhayyim.com'
      )
    WHEN owner_did LIKE 'did:web:%'
      THEN CONCAT('did:web:', SPLIT_PART(SPLIT_PART(owner_did, ':', 3), '/', 1))
    ELSE owner_did
  END AS canonical_actor_did,
  COUNT(*)::BIGINT AS page_count
FROM vertex_page
WHERE owner_did IS NOT NULL AND owner_did <> ''
GROUP BY 1
