-- Telecom optical link state: OTN connection counts per ODU/client/protection/status.
MODEL (
  name dev.mv_telecom_optical_link_state,
  kind FULL,
  dialect postgres,
  description 'Per (odu_kind, client_service_kind, protection_kind, status): OTN connection count.',
  grain [odu_kind, client_service_kind, protection_kind, status],
  tags [telecom, optical, otn, link]
);

SELECT
  odu_kind,
  client_service_kind,
  protection_kind,
  status,
  COUNT(*) AS otn_count
FROM vertex_telecom_optical_otn_connection
GROUP BY odu_kind, client_service_kind, protection_kind, status
