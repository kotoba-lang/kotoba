-- Telecom NFV heal summary: heal event counts per cause/kind/status.
MODEL (
  name dev.mv_telecom_nfv_heal_summary,
  kind FULL,
  dialect postgres,
  description 'Per (heal_cause, heal_kind, status): heal event count from NFV.',
  grain [heal_cause, heal_kind, status],
  tags [telecom, nfv, heal]
);

SELECT
  heal_cause,
  heal_kind,
  status,
  COUNT(*) AS event_count
FROM vertex_telecom_nfv_heal_event
GROUP BY heal_cause, heal_kind, status
