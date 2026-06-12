-- Fukkou flow by category: budget flow totals per year, category, and actor pair.
MODEL (
  name dev.mv_fukkou_flow_by_category,
  kind FULL,
  dialect postgres,
  description 'Per (fiscal_year, category, source_kind, destination_kind): flow count and total JPY.',
  grain [fiscal_year, category, source_kind, destination_kind],
  tags [fukkou, budget, flow, category]
);

SELECT
  fiscal_year,
  category,
  source_kind,
  destination_kind,
  COUNT(*) AS flow_count,
  SUM(amount_jpy) AS total_jpy
FROM vertex_fukkou_budget_flow
GROUP BY fiscal_year, category, source_kind, destination_kind
