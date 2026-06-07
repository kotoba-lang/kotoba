-- Telecom MEC relocation summary: EAS relocation counts per trigger/mode/status.
MODEL (
  name dev.mv_telecom_mec_relocation_summary,
  kind FULL,
  dialect postgres,
  description 'Per (trigger_kind, acr_mode, status): MEC EAS relocation count.',
  grain [trigger_kind, acr_mode, status],
  tags [telecom, mec, relocation]
);

SELECT
  trigger_kind,
  acr_mode,
  status,
  COUNT(*) AS relocation_count
FROM vertex_telecom_mec_eas_relocation
GROUP BY trigger_kind, acr_mode, status
