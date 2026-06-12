-- Telecom TSN bridge inventory: TSN bridge counts per vendor/kind/status.
MODEL (
  name dev.mv_telecom_tsn_bridge_inventory,
  kind FULL,
  dialect postgres,
  description 'Per (vendor, bridge_kind, status): TSN bridge count.',
  grain [vendor, bridge_kind, status],
  tags [telecom, tsn, bridge, inventory]
);

SELECT
  vendor,
  bridge_kind,
  status,
  COUNT(*) AS bridge_count
FROM vertex_telecom_tsn_bridge
GROUP BY vendor, bridge_kind, status
