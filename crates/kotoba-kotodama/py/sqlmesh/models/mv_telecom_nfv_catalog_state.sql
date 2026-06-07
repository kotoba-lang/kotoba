-- Telecom NFV catalog state: NSD and VNFD descriptor counts per vendor/format/status.
MODEL (
  name dev.mv_telecom_nfv_catalog_state,
  kind FULL,
  dialect postgres,
  description 'Per (desc_kind=nsd|vnfd, vendor, descriptor_format, status): descriptor count.',
  grain [desc_kind, vendor, descriptor_format, status],
  tags [telecom, nfv, catalog]
);

SELECT 'nsd' AS desc_kind, vendor, descriptor_format, status, COUNT(*) AS desc_count
FROM vertex_telecom_nfv_nsd
GROUP BY vendor, descriptor_format, status
UNION ALL
SELECT 'vnfd' AS desc_kind, vendor, descriptor_format, status, COUNT(*) AS desc_count
FROM vertex_telecom_nfv_vnfd
GROUP BY vendor, descriptor_format, status
