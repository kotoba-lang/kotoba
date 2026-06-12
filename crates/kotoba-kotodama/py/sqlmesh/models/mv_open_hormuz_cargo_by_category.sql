-- Open Hormuz cargo by category: declared manifest aggregates per cargo category and destination.
MODEL (
  name dev.mv_open_hormuz_cargo_by_category,
  kind FULL,
  dialect postgres,
  description 'Per (cargo_category, destination_port_locode): manifest count, total volume/value, latest declared.',
  grain [cargo_category, destination_port_locode],
  tags [open_hormuz, cargo, manifest]
);

SELECT
  cargo_category,
  destination_port_locode,
  COUNT(*) AS manifest_count,
  SUM(volume_tonnes) AS total_volume,
  SUM(value_usd) AS total_value,
  MAX(declared_at) AS latest_declared
FROM vertex_open_hormuz_cargo_manifest
WHERE status = 'declared'
GROUP BY cargo_category, destination_port_locode
