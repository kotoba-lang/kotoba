-- Lawfirm e-sign active: pending e-signature requests in flight.
MODEL (
  name dev.mv_lawfirm_esign_active,
  kind FULL,
  dialect postgres,
  description 'Per envelope (status sent or delivered): provider, document kind, matter URI, expiry.',
  grain [envelope_id],
  tags [lawfirm, esign, active]
);

SELECT
  envelope_id,
  provider,
  document_kind,
  matter_uri,
  status,
  expires_at,
  created_at,
  updated_at
FROM vertex_lawfirm_esign_request
WHERE status IN ('sent', 'delivered')
