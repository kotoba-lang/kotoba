-- Open sales pipeline health: open opportunity aggregates per stage with weighted USD.
MODEL (
  name dev.mv_open_sales_pipeline_health,
  kind FULL,
  dialect postgres,
  description 'Per stage (open opps): count, total USD, avg probability, weighted USD.',
  grain [stage],
  tags [open_sales, pipeline, health, opportunity]
);

SELECT
  stage,
  COUNT(*) AS opp_count,
  SUM(amount_usd) AS total_pipeline_usd,
  AVG(probability_pct) AS avg_probability_pct,
  SUM(amount_usd * probability_pct / 100.0) AS weighted_usd
FROM vertex_open_sales_opportunity
WHERE status = 'open'
GROUP BY stage
