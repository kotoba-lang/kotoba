-- Telecom NTN partner state: NTN partner counts per constellation/settlement/status.
MODEL (
  name dev.mv_telecom_ntn_partner_state,
  kind FULL,
  dialect postgres,
  description 'Per (constellation_kind, settlement_mode, status): NTN partner count.',
  grain [constellation_kind, settlement_mode, status],
  tags [telecom, ntn, partner]
);

SELECT
  constellation_kind,
  settlement_mode,
  status,
  COUNT(*) AS partner_count
FROM vertex_telecom_ntn_partner
GROUP BY constellation_kind, settlement_mode, status
