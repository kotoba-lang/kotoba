-- Telecom NTN handover summary: handover counts and timing aggregates per kind/trigger/status.
MODEL (
  name dev.mv_telecom_ntn_handover_summary,
  kind FULL,
  dialect postgres,
  description 'Per (handover_kind, trigger_kind, status): handover count, avg doppler Hz, avg one-way delay ms.',
  grain [handover_kind, trigger_kind, status],
  tags [telecom, ntn, handover]
);

SELECT
  handover_kind,
  trigger_kind,
  status,
  COUNT(*) AS handover_count,
  AVG(doppler_offset_hz) AS avg_doppler_hz,
  AVG(one_way_delay_ms) AS avg_owd_ms
FROM vertex_telecom_ntn_handover
GROUP BY handover_kind, trigger_kind, status
