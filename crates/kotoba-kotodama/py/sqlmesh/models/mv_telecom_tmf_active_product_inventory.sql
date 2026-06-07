-- Telecom TMF active product inventory: TMF products in Active lifecycle.
MODEL (
  name dev.mv_telecom_tmf_active_product_inventory,
  kind FULL,
  dialect postgres,
  description 'Per TMF product inventory record with lifecycle Active: id, account, started_at, org.',
  grain [record_id],
  tags [telecom, tmf, product, inventory, active]
);

SELECT
  record_id,
  product_id,
  account_id,
  lifecycle_status,
  started_at,
  org_id
FROM vertex_telecom_tmf_product_inventory
WHERE lifecycle_status = 'Active'
