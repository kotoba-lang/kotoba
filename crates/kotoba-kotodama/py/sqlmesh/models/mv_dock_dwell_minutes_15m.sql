-- Dock dwell-time KPI per door, 15-minute tumbling window.
-- Cost compression goal: drive `avg_dwell_min` and `p95_dwell_min` down.
MODEL (
  name dev.mv_dock_dwell_minutes_15m,
  kind FULL,
  dialect postgres,
  description 'Dock dwell-time aggregates per door per 15-minute window.',
  grain [bucket_ts, dock_door_code],
  tags [yard_ops, cost_kpi, dwell, window_15m]
);

SELECT
  date_trunc('hour', CAST(c.created_at AS timestamp))
    + INTERVAL '15 minutes'
      * (EXTRACT(MINUTE FROM CAST(c.created_at AS timestamp))::int / 15) AS bucket_ts,
  COALESCE(j.value_json::json ->> 'dockDoorCode', 'unknown') AS dock_door_code,
  COUNT(*)                                                          AS completion_count,
  AVG(CAST(c.value_json::json ->> 'actualDurationMin' AS double precision))   AS avg_dwell_min,
  MIN(CAST(c.value_json::json ->> 'actualDurationMin' AS double precision))   AS min_dwell_min,
  MAX(CAST(c.value_json::json ->> 'actualDurationMin' AS double precision))   AS max_dwell_min,
  PERCENTILE_CONT(0.95) WITHIN GROUP (
    ORDER BY CAST(c.value_json::json ->> 'actualDurationMin' AS double precision)
  )                                                                  AS p95_dwell_min
FROM vertex_yard_ops_dock_completion c
LEFT JOIN vertex_yard_ops_dock_job   j
  ON j.vertex_id = c.value_json::json ->> 'dockJobVertexId'
WHERE c.status = 'closed'
GROUP BY 1, 2
