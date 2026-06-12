-- Telecom SEPP key rotation summary: SEPP key rotation counts per kind/reason.
MODEL (
  name dev.mv_telecom_sepp_key_rotation_summary,
  kind FULL,
  dialect postgres,
  description 'Per (key_kind, rotation_reason): key rotation count from vertex_telecom_sepp_key_rotation.',
  grain [key_kind, rotation_reason],
  tags [telecom, 5g, sepp, key_rotation]
);

SELECT
  key_kind,
  rotation_reason,
  COUNT(*) AS rotation_count
FROM vertex_telecom_sepp_key_rotation
GROUP BY key_kind, rotation_reason
