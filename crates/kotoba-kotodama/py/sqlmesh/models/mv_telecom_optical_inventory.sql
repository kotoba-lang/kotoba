-- Telecom optical inventory: union of OLS / ROADM / fiber span counts per vendor/status.
MODEL (
  name dev.mv_telecom_optical_inventory,
  kind FULL,
  dialect postgres,
  description 'Per (kind=ols|roadm|fiber_span, vendor, status): count from optical inventory tables.',
  grain [kind, vendor, status],
  tags [telecom, optical, inventory]
);

SELECT 'ols' AS kind, vendor, status, COUNT(*) AS count_value FROM vertex_telecom_optical_ols GROUP BY vendor, status
UNION ALL
SELECT 'roadm' AS kind, wss_vendor AS vendor, status, COUNT(*) AS count_value FROM vertex_telecom_optical_roadm GROUP BY wss_vendor, status
UNION ALL
SELECT 'fiber_span' AS kind, owner_org_id AS vendor, status, COUNT(*) AS count_value FROM vertex_telecom_optical_fiber_span GROUP BY owner_org_id, status
