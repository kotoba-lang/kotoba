-- Telecom TMF open product orders: TMF product orders not in terminal state.
MODEL (
  name dev.mv_telecom_tmf_open_product_orders,
  kind FULL,
  dialect postgres,
  description 'TMF product orders excluding completed/cancelled/rejected statuses.',
  grain [product_order_id],
  tags [telecom, tmf, product_order, open]
);

SELECT
  product_order_id,
  account_id,
  order_kind,
  offering_id,
  priority,
  observed_at,
  status,
  org_id
FROM vertex_telecom_tmf_product_order
WHERE status NOT IN ('completed', 'cancelled', 'rejected')
