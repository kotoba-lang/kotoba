-- Telecom O-RAN app inventory: rApp and xApp counts per vendor/status.
MODEL (
  name dev.mv_telecom_oran_app_inventory,
  kind FULL,
  dialect postgres,
  description 'Per (app_kind=rapp|xapp, vendor, status): O-RAN app count.',
  grain [app_kind, vendor, status],
  tags [telecom, oran, app, inventory]
);

SELECT 'rapp' AS app_kind, vendor, status, COUNT(*) AS app_count
FROM vertex_telecom_oran_rapp
GROUP BY vendor, status
UNION ALL
SELECT 'xapp' AS app_kind, vendor, status, COUNT(*) AS app_count
FROM vertex_telecom_oran_xapp
GROUP BY vendor, status
