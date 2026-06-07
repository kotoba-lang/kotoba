-- Telecom optical channel state: DWDM channel counts and total line rate per modulation/FEC/status.
MODEL (
  name dev.mv_telecom_optical_channel_state,
  kind FULL,
  dialect postgres,
  description 'Per (modulation, fec, status): DWDM channel count and total line rate Gbps.',
  grain [modulation, fec, status],
  tags [telecom, optical, dwdm, channel]
);

SELECT
  modulation,
  fec,
  status,
  COUNT(*) AS channel_count,
  SUM(line_rate_gbps) AS total_line_rate_gbps
FROM vertex_telecom_optical_dwdm_channel
GROUP BY modulation, fec, status
