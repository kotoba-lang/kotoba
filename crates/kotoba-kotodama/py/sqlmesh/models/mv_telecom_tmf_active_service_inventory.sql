-- Telecom TMF active service inventory: TMF services in active lifecycle.
MODEL (
  name dev.mv_telecom_tmf_active_service_inventory,
  kind FULL,
  dialect postgres,
  description 'Per TMF service inventory record with lifecycle active: kind, vid, operational state, started_at.',
  grain [record_id],
  tags [telecom, tmf, service, inventory, active]
);

SELECT
  record_id,
  service_instance_kind,
  service_instance_vid,
  lifecycle_status,
  operational_state,
  started_at,
  org_id
FROM vertex_telecom_tmf_service_inventory
WHERE lifecycle_status = 'active'
