-- Etzhayyim identity children: child count per parent DID and segment kind.
MODEL (
  name dev.mv_etzhayyim_identity_children,
  kind FULL,
  dialect postgres,
  description 'Per (parent_did, segment_kind): total child count and active (non-revoked) child count.',
  grain [parent_did, segment_kind],
  tags [etzhayyim, did, identity, children]
);

SELECT
  parent_did,
  segment_kind,
  COUNT(*) AS child_count,
  COUNT(*) FILTER (WHERE revoked_at IS NULL) AS active_child_count
FROM vertex_etzhayyim_identity
WHERE parent_did IS NOT NULL
GROUP BY parent_did, segment_kind
