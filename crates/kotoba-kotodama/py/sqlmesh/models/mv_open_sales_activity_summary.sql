-- Open sales activity summary: activity counts per opportunity and kind.
MODEL (
  name dev.mv_open_sales_activity_summary,
  kind FULL,
  dialect postgres,
  description 'Per (opp_did, kind): activity count from vertex_open_sales_activity.',
  grain [opp_did, kind],
  tags [open_sales, activity]
);

SELECT
  opp_did,
  kind,
  COUNT(*) AS activity_count
FROM vertex_open_sales_activity
GROUP BY opp_did, kind
