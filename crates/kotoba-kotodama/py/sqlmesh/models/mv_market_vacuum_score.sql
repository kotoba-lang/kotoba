-- Market vacuum score: per-(lane, date) demand vs supply gap.
MODEL (
  name dev.mv_market_vacuum_score,
  kind FULL,
  dialect postgres,
  description 'Per (lane, observed_date): demand_total, supply_settled (mokuteki floor pass), and vacuum_score gap.',
  grain [lane, observed_date],
  tags [market, vacuum, supply, demand]
);

SELECT
  d.lane AS lane,
  d.created_date AS observed_date,
  COALESCE(SUM(d.magnitude), 0.0) AS demand_total,
  COALESCE((
    SELECT SUM(s.total_price)
    FROM vertex_market_settlement s
    WHERE s.lane = d.lane
      AND s.created_date = d.created_date
      AND s.mokuteki_floor_pass = TRUE
      AND s.status = 'settled'
  ), 0.0) AS supply_settled,
  COALESCE(SUM(d.magnitude), 0.0) - COALESCE((
    SELECT SUM(s.total_price)
    FROM vertex_market_settlement s
    WHERE s.lane = d.lane
      AND s.created_date = d.created_date
      AND s.mokuteki_floor_pass = TRUE
      AND s.status = 'settled'
  ), 0.0) AS vacuum_score,
  COUNT(*) AS demand_observation_count
FROM vertex_market_demand_signal d
GROUP BY d.lane, d.created_date
