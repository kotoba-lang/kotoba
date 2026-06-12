-- Telecom NFV scale summary: scale event counts and total delta per kind/direction/trigger.
MODEL (
  name dev.mv_telecom_nfv_scale_summary,
  kind FULL,
  dialect postgres,
  description 'Per (scale_kind, scale_direction, trigger_kind): scale event count and total delta.',
  grain [scale_kind, scale_direction, trigger_kind],
  tags [telecom, nfv, scale, summary]
);

SELECT
  scale_kind,
  scale_direction,
  trigger_kind,
  COUNT(*) AS event_count,
  SUM(delta) AS total_delta
FROM vertex_telecom_nfv_scale_event
GROUP BY scale_kind, scale_direction, trigger_kind
