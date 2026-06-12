-- Monthly burn rate by cost center category.
MODEL (
  name dev.mv_burn_rate_monthly,
  kind FULL,
  dialect postgres,
  description 'Per category: center count, total monthly burn (JPY), reducible burn, and planned reduction from edge_reduces_cost.',
  grain [category],
  tags [strategy, cost, burn_rate, monthly, reduction]
);

SELECT
  cc.category,
  COUNT(*) AS center_count,
  SUM(cc.monthly_burn_jpy) AS total_burn,
  SUM(cc.monthly_burn_jpy * cc.reducible_bps / 10000) AS reducible_burn,
  SUM(rc.monthly_reduction_jpy) AS planned_reduction
FROM vertex_cost_center cc
LEFT JOIN edge_reduces_cost rc ON rc.dst_vid = cc.vertex_id
GROUP BY cc.category
