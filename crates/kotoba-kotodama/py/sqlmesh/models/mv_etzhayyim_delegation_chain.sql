-- Etzhayyim delegation chain: flat projection of delegation edges.
MODEL (
  name dev.mv_etzhayyim_delegation_chain,
  kind FULL,
  dialect postgres,
  description 'Per delegation edge: delegatee DID, delegator DID, RACI role, scope.',
  grain [delegatee_did, delegator_did],
  tags [etzhayyim, delegation, raci, identity]
);

SELECT
  dst_vid AS delegatee_did,
  src_vid AS delegator_did,
  raci,
  role,
  scope
FROM edge_etzhayyim_delegates_to
