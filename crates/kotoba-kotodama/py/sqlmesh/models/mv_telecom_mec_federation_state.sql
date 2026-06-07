-- Telecom MEC federation state: federation counts per kind/billing/status.
MODEL (
  name dev.mv_telecom_mec_federation_state,
  kind FULL,
  dialect postgres,
  description 'Per (federation_kind, billing_mode, status): MEC federation count.',
  grain [federation_kind, billing_mode, status],
  tags [telecom, mec, federation]
);

SELECT
  federation_kind,
  billing_mode,
  status,
  COUNT(*) AS federation_count
FROM vertex_telecom_mec_federation
GROUP BY federation_kind, billing_mode, status
