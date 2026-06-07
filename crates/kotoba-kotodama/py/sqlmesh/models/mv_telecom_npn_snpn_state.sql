-- Telecom NPN SNPN state: SNPN deployment counts per kind/jurisdiction/status.
MODEL (
  name dev.mv_telecom_npn_snpn_state,
  kind FULL,
  dialect postgres,
  description 'Per (deployment_kind, jurisdiction, status): SNPN deployment count.',
  grain [deployment_kind, jurisdiction, status],
  tags [telecom, npn, snpn]
);

SELECT
  deployment_kind,
  jurisdiction,
  status,
  COUNT(*) AS deployment_count
FROM vertex_telecom_npn_snpn_deployment
GROUP BY deployment_kind, jurisdiction, status
