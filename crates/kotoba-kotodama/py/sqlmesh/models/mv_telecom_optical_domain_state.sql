-- Telecom optical domain state: optical domain counts per controller/jurisdiction/status.
MODEL (
  name dev.mv_telecom_optical_domain_state,
  kind FULL,
  dialect postgres,
  description 'Per (controller_kind, jurisdiction, status): optical domain count.',
  grain [controller_kind, jurisdiction, status],
  tags [telecom, optical, domain]
);

SELECT
  controller_kind,
  jurisdiction,
  status,
  COUNT(*) AS domain_count
FROM vertex_telecom_optical_domain
GROUP BY controller_kind, jurisdiction, status
