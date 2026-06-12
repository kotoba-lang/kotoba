-- Airline cargo revenue: total weight and rate-weighted revenue per confirmed booking route.
MODEL (
  name dev.mv_air_cargo_revenue,
  kind FULL,
  dialect postgres,
  description 'Total weight_kg and rate-weighted revenue per origin/dest/carrier from vertex_air_cargo_booking.',
  grain [origin, dest, carrier_code],
  tags [air, cargo, revenue, weight, route]
);

SELECT
  origin,
  dest,
  carrier_code,
  SUM(weight_kg) AS total_weight_kg,
  SUM(rate * weight_kg) AS total_revenue
FROM vertex_air_cargo_booking
WHERE status = 'confirmed'
GROUP BY origin, dest, carrier_code
