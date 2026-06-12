-- Flight operator KPI daily: per-operator daily flight performance metrics.
MODEL (
  name dev.mv_flight_operator_kpi_daily,
  kind FULL,
  dialect postgres,
  description 'Per (operator_did, day): flight count, avg delay, avg occupancy, total revenue/cost/profit.',
  grain [operator_did, day],
  tags [flight, operator, kpi, daily, revenue, delay]
);

SELECT
  operator_did,
  SUBSTRING(COALESCE(as_of, created_date::VARCHAR), 1, 10) AS day,
  COUNT(*)::BIGINT AS flight_count,
  AVG(delay_minutes)::DOUBLE PRECISION AS avg_delay_minutes,
  AVG(occupancy_rate)::DOUBLE PRECISION AS avg_occupancy_rate,
  SUM(COALESCE(revenue, 0))::DOUBLE PRECISION AS total_revenue,
  SUM(COALESCE(cost, 0))::DOUBLE PRECISION AS total_cost,
  SUM(COALESCE(profit, COALESCE(revenue, 0) - COALESCE(cost, 0)))::DOUBLE PRECISION AS total_profit
FROM vertex_flight_operation
WHERE operator_did IS NOT NULL AND operator_did <> ''
GROUP BY operator_did, SUBSTRING(COALESCE(as_of, created_date::VARCHAR), 1, 10)
