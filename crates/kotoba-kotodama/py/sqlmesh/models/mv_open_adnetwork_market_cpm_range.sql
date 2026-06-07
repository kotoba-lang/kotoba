-- Open ad network market CPM range: floor CPM stats per ad unit type.
MODEL (
  name dev.mv_open_adnetwork_market_cpm_range,
  kind FULL,
  dialect postgres,
  description 'Per unit_type: active unit count, min/avg/max floor_cpm_usd.',
  grain [unit_type],
  tags [open_adnetwork, market, cpm, floor]
);

SELECT
  unit_type,
  COUNT(*) AS unit_count,
  MIN(floor_cpm_usd) AS min_floor_cpm,
  AVG(floor_cpm_usd) AS avg_floor_cpm,
  MAX(floor_cpm_usd) AS max_floor_cpm
FROM vertex_open_adnetwork_ad_unit
WHERE status = 'active'
GROUP BY unit_type
