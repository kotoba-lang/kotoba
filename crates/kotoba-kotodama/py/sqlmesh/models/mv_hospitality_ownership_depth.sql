-- Hospitality ownership depth: direct children count per parent under hospitality DID prefix.
MODEL (
  name dev.mv_hospitality_ownership_depth,
  kind FULL,
  dialect postgres,
  description 'Per parent_did: direct children count and max _seq from edge_owned_by for hospitality actors.',
  grain [parent_did],
  tags [hospitality, ownership, depth]
);

SELECT
  src_vid AS parent_did,
  COUNT(*) AS direct_children,
  MAX(_seq) AS last_seq
FROM edge_owned_by
WHERE src_vid LIKE 'did:web:hospitality.etzhayyim.com:%'
GROUP BY src_vid
