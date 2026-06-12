-- Open sales stage velocity: per-stage opportunity counts with won/lost outcomes.
MODEL (
  name dev.mv_open_sales_stage_velocity,
  kind FULL,
  dialect postgres,
  description 'Per stage (all opps): count, avg deal size, won/lost counts.',
  grain [stage],
  tags [open_sales, stage, velocity]
);

SELECT
  stage,
  COUNT(*) AS opp_count,
  AVG(amount_usd) AS avg_deal_size_usd,
  SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) AS won_count,
  SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) AS lost_count
FROM vertex_open_sales_opportunity
GROUP BY stage
