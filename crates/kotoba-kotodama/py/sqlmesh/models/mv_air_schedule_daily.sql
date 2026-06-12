-- Active airline schedule: flight count and dep/arr time range per route and carrier.
MODEL (
  name dev.mv_air_schedule_daily,
  kind FULL,
  dialect postgres,
  description 'Count of active scheduled flights per origin/dest/carrier with first/last dep-arr times.',
  grain [origin, dest, carrier_code],
  tags [air, schedule, daily, route, carrier]
);

SELECT
  origin,
  dest,
  carrier_code,
  COUNT(*) AS flight_count,
  MIN(dep_time) AS first_dep,
  MAX(arr_time) AS last_arr
FROM vertex_air_sched_schedule
WHERE status = 'active'
GROUP BY origin, dest, carrier_code
