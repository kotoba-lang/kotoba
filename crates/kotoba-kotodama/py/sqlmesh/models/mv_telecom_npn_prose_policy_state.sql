-- Telecom NPN ProSe policy state: ProSe policy counts per kind/profile/status.
MODEL (
  name dev.mv_telecom_npn_prose_policy_state,
  kind FULL,
  dialect postgres,
  description 'Per (communication_kind, sidelink_profile, status): ProSe policy count.',
  grain [communication_kind, sidelink_profile, status],
  tags [telecom, npn, prose, policy]
);

SELECT
  communication_kind,
  sidelink_profile,
  status,
  COUNT(*) AS policy_count
FROM vertex_telecom_npn_prose_policy
GROUP BY communication_kind, sidelink_profile, status
