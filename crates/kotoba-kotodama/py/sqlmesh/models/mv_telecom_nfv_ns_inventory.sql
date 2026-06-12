-- Telecom NFV NS inventory: NFV network service counts per flavor/slice/status.
MODEL (
  name dev.mv_telecom_nfv_ns_inventory,
  kind FULL,
  dialect postgres,
  description 'Per (deployment_flavor, snssai, status): NS count from vertex_telecom_nfv_ns.',
  grain [deployment_flavor, snssai, status],
  tags [telecom, nfv, ns, inventory]
);

SELECT
  deployment_flavor,
  snssai,
  status,
  COUNT(*) AS ns_count
FROM vertex_telecom_nfv_ns
GROUP BY deployment_flavor, snssai, status
