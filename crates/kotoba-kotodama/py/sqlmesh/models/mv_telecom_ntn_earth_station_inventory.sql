-- Telecom NTN earth station inventory: earth station counts per operator/kind/jurisdiction.
MODEL (
  name dev.mv_telecom_ntn_earth_station_inventory,
  kind FULL,
  dialect postgres,
  description 'Per (operator_org_id, station_kind, jurisdiction, status): earth station count.',
  grain [operator_org_id, station_kind, jurisdiction, status],
  tags [telecom, ntn, earth_station, inventory]
);

SELECT
  operator_org_id,
  station_kind,
  jurisdiction,
  status,
  COUNT(*) AS station_count
FROM vertex_telecom_ntn_earth_station
GROUP BY operator_org_id, station_kind, jurisdiction, status
