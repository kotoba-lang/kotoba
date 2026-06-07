-- Telecom WLAN roaming AAA health: WLAN roaming exchange counts per transport/peer/message/result.
MODEL (
  name dev.mv_telecom_wlan_roaming_aaa_health,
  kind FULL,
  dialect postgres,
  description 'Per (transport_kind, peer_kind, message_kind, result_code): exchange count.',
  grain [transport_kind, peer_kind, message_kind, result_code],
  tags [telecom, wlan, roaming, aaa]
);

SELECT
  transport_kind,
  peer_kind,
  message_kind,
  result_code,
  COUNT(*) AS exchange_count
FROM vertex_telecom_wlan_roaming_exchange
GROUP BY transport_kind, peer_kind, message_kind, result_code
