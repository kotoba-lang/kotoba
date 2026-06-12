-- Telecom NF topology: 5G core network function instance counts per type/PLMN/status.
MODEL (
  name dev.mv_telecom_nf_topology,
  kind FULL,
  dialect postgres,
  description 'Per (nf_type, plmn_id, status): NF instance count from vertex_telecom_nf_instance.',
  grain [nf_type, plmn_id, status],
  tags [telecom, 5g, nf, topology]
);

SELECT
  nf_type,
  plmn_id,
  status,
  COUNT(*) AS instance_count
FROM vertex_telecom_nf_instance
GROUP BY nf_type, plmn_id, status
