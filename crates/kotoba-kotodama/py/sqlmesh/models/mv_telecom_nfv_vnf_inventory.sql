-- Telecom NFV VNF inventory: VNF counts per VIM/flavor/status.
MODEL (
  name dev.mv_telecom_nfv_vnf_inventory,
  kind FULL,
  dialect postgres,
  description 'Per (vim_id, deployment_flavor, status): VNF count from vertex_telecom_nfv_vnf.',
  grain [vim_id, deployment_flavor, status],
  tags [telecom, nfv, vnf, inventory]
);

SELECT
  vim_id,
  deployment_flavor,
  status,
  COUNT(*) AS vnf_count
FROM vertex_telecom_nfv_vnf
GROUP BY vim_id, deployment_flavor, status
