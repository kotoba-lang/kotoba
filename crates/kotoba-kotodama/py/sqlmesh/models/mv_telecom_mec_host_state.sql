-- Telecom MEC host state: MEC host counts per vendor/zone/PLMN/status.
MODEL (
  name dev.mv_telecom_mec_host_state,
  kind FULL,
  dialect postgres,
  description 'Per (vendor, edge_zone, plmn_id, status): MEC host count.',
  grain [vendor, edge_zone, plmn_id, status],
  tags [telecom, mec, host]
);

SELECT
  vendor,
  edge_zone,
  plmn_id,
  status,
  COUNT(*) AS host_count
FROM vertex_telecom_mec_host
GROUP BY vendor, edge_zone, plmn_id, status
