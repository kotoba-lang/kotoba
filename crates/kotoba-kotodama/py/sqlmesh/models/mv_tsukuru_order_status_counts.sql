-- Tsukuru order status counts: production order count per status.
MODEL (
  name dev.mv_tsukuru_order_status_counts,
  kind FULL,
  dialect postgres,
  description 'Per status: production order count from vertex_tsukuru_production_order.',
  grain [status],
  tags [tsukuru, production_order, status, count]
);

SELECT
  value_json::JSONB ->> 'status' AS status,
  COUNT(*) AS cnt
FROM vertex_tsukuru_production_order
GROUP BY value_json::JSONB ->> 'status'
