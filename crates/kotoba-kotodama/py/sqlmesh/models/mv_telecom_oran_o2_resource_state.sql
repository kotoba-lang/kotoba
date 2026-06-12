-- Telecom O-RAN O2 resource state: O2 resource counts per interface/kind/manager/status.
MODEL (
  name dev.mv_telecom_oran_o2_resource_state,
  kind FULL,
  dialect postgres,
  description 'Per (interface_kind, resource_kind, deployment_manager, status): O2 resource count.',
  grain [interface_kind, resource_kind, deployment_manager, status],
  tags [telecom, oran, o2, resource]
);

SELECT
  interface_kind,
  resource_kind,
  deployment_manager,
  status,
  COUNT(*) AS resource_count
FROM vertex_telecom_oran_o2_resource
GROUP BY interface_kind, resource_kind, deployment_manager, status
