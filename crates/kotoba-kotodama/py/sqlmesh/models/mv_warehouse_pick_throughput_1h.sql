-- Warehouse pick throughput per SKU, 1-hour tumbling window.
-- Cost compression goal: maximize picks/hour while keeping bin-spread low.
MODEL (
  name dev.mv_warehouse_pick_throughput_1h,
  kind FULL,
  dialect postgres,
  description 'Pick throughput aggregates per SKU per 1-hour window.',
  grain [bucket_ts, sku_code],
  tags [warehouse, cost_kpi, throughput, window_1h]
);

SELECT
  date_trunc('hour', CAST(p.created_at AS timestamp)) AS bucket_ts,
  COALESCE(p.value_json::json ->> 'skuCode', 'unknown') AS sku_code,
  COUNT(*)                                              AS pick_count,
  SUM(CAST(p.value_json::json ->> 'quantity' AS double precision)) AS picked_qty_total,
  AVG(json_array_length(p.value_json::json -> 'bins'))  AS avg_bins_per_pick
FROM vertex_warehouse_pick p
WHERE p.status = 'active'
GROUP BY 1, 2
