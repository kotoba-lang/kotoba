-- Telecom TSN sync health: TSN sync deviation event counts and offset stats.
MODEL (
  name dev.mv_telecom_tsn_sync_health,
  kind FULL,
  dialect postgres,
  description 'Per (deviation_kind, breach): event count, avg/max offset_ns.',
  grain [deviation_kind, breach],
  tags [telecom, tsn, sync, deviation]
);

SELECT
  deviation_kind,
  breach,
  COUNT(*) AS event_count,
  AVG(offset_ns) AS avg_offset_ns,
  MAX(offset_ns) AS max_offset_ns
FROM vertex_telecom_tsn_sync_deviation
GROUP BY deviation_kind, breach
