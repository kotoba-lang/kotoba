-- Telecom TMF open service orders: TMF service orders not in terminal state.
MODEL (
  name dev.mv_telecom_tmf_open_service_orders,
  kind FULL,
  dialect postgres,
  description 'TMF service orders excluding completed/cancelled/rejected statuses.',
  grain [service_order_id],
  tags [telecom, tmf, service_order, open]
);

SELECT
  service_order_id,
  product_order_id,
  order_kind,
  service_spec,
  observed_at,
  status,
  org_id
FROM vertex_telecom_tmf_service_order
WHERE status NOT IN ('completed', 'cancelled', 'rejected')
