-- Datacenter active incidents: flat projection of open incident operations.
MODEL (
  name dev.mv_datacenter_active_incident,
  kind FULL,
  dialect postgres,
  description 'Active datacenter incident rows from vertex_datacenter_operation where operation_kind=incident.',
  grain [vertex_id],
  tags [datacenter, incident, operations, status, monitoring]
);

SELECT
  facility_id,
  vertex_id,
  operation_kind,
  risk_class,
  status,
  customer_impact,
  metric_ref,
  opened_at,
  reviewed_at,
  approved_at,
  stabilized_at
FROM vertex_datacenter_operation
WHERE operation_kind = 'incident'
