-- Telecom NTN satellite inventory: satellite counts per operator/orbit/status.
MODEL (
  name dev.mv_telecom_ntn_satellite_inventory,
  kind FULL,
  dialect postgres,
  description 'Per (operator_org_id, orbit_class, status): satellite count.',
  grain [operator_org_id, orbit_class, status],
  tags [telecom, ntn, satellite, inventory]
);

SELECT
  operator_org_id,
  orbit_class,
  status,
  COUNT(*) AS satellite_count
FROM vertex_telecom_ntn_satellite
GROUP BY operator_org_id, orbit_class, status
