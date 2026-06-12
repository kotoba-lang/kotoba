-- Open JPN MyNumber OAuth token status: derived status from active/revoked flags.
MODEL (
  name dev.mv_open_jpn_mynumber_oauth_token_status,
  kind FULL,
  dialect postgres,
  description 'Per OAuth token: requester, scope, expiry/revoke metadata, derived status (active/revoked/inactive).',
  grain [token_ref],
  tags [open_jpn, mynumber, oauth, token, status]
);

SELECT
  vertex_id AS token_ref,
  requester_agency,
  purpose_code,
  scope_json,
  active,
  expires_at,
  revoked_at,
  created_at,
  CASE
    WHEN active IS TRUE AND revoked_at IS NULL THEN 'active'
    WHEN revoked_at IS NOT NULL THEN 'revoked'
    ELSE 'inactive'
  END AS status
FROM vertex_open_jpn_mynumber_oauth_token
