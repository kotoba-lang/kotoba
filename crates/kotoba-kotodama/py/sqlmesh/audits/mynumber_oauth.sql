-- SQLMesh audit: mv_open_jpn_mynumber_oauth_token_status invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_mynumber_oauth_status_known,
  model dev.mv_open_jpn_mynumber_oauth_token_status,
  dialect postgres,
  description 'derived status must be one of active/revoked/inactive.'
);
SELECT *
FROM dev.mv_open_jpn_mynumber_oauth_token_status
WHERE status NOT IN ('active', 'revoked', 'inactive');

---

AUDIT (
  name assert_mynumber_oauth_revoked_consistency,
  model dev.mv_open_jpn_mynumber_oauth_token_status,
  dialect postgres,
  description 'status=revoked implies revoked_at NOT NULL; status=active implies revoked_at NULL.'
);
SELECT *
FROM dev.mv_open_jpn_mynumber_oauth_token_status
WHERE (status = 'revoked' AND revoked_at IS NULL)
   OR (status = 'active' AND revoked_at IS NOT NULL);
