-- Game sales by region: annual units and revenue per region.
MODEL (
  name dev.mv_game_sales_by_region,
  kind FULL,
  dialect postgres,
  description 'Per (region, year): total units sold, revenue, and distinct title count.',
  grain [region, year],
  tags [game, sales, region, revenue]
);

SELECT
  region,
  year,
  SUM(units_sold)::BIGINT AS units_year,
  SUM(revenue_usd) AS revenue_year,
  COUNT(DISTINCT title_did) AS title_count
FROM vertex_game_sales_monthly
GROUP BY region, year
