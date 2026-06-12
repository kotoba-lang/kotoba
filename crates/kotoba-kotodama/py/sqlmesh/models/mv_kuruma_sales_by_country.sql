-- Kuruma sales by country: annual units and revenue per model and country.
MODEL (
  name dev.mv_kuruma_sales_by_country,
  kind FULL,
  dialect postgres,
  description 'Per (model_did, country, year): total units sold and revenue in USD.',
  grain [model_did, country, year],
  tags [kuruma, sales, country, revenue]
);

SELECT
  s.model_did,
  s.country,
  s.year,
  SUM(s.units_sold)::BIGINT AS units_sold_year,
  SUM(s.revenue_usd) AS revenue_year
FROM vertex_kuruma_sales_monthly s
GROUP BY s.model_did, s.country, s.year
