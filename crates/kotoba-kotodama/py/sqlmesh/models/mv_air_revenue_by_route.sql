-- Airline yield revenue and average load factor per route and carrier.
MODEL (
  name dev.mv_air_revenue_by_route,
  kind FULL,
  dialect postgres,
  description 'Average load factor and total revenue per origin/dest/carrier from vertex_air_yield_control.',
  grain [origin, dest, carrier_code],
  tags [air, revenue, yield, route, load_factor]
);

SELECT
  origin,
  dest,
  carrier_code,
  AVG(load_factor) AS avg_lf,
  SUM(revenue) AS total_revenue
FROM vertex_air_yield_control
GROUP BY origin, dest, carrier_code
