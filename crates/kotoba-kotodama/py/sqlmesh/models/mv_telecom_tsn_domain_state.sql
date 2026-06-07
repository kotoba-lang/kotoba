-- Telecom TSN domain state: TSN domain counts per profile/controller/status.
MODEL (
  name dev.mv_telecom_tsn_domain_state,
  kind FULL,
  dialect postgres,
  description 'Per (profile_kind, controller_kind, status): TSN domain count.',
  grain [profile_kind, controller_kind, status],
  tags [telecom, tsn, domain]
);

SELECT
  profile_kind,
  controller_kind,
  status,
  COUNT(*) AS domain_count
FROM vertex_telecom_tsn_domain
GROUP BY profile_kind, controller_kind, status
