-- Telecom O-RAN O1 config state: O1 configuration operation counts per target/transport/operation/status.
MODEL (
  name dev.mv_telecom_oran_o1_config_state,
  kind FULL,
  dialect postgres,
  description 'Per (target_kind, interface_transport, operation, status): O1 config count.',
  grain [target_kind, interface_transport, operation, status],
  tags [telecom, oran, o1, config]
);

SELECT
  target_kind,
  interface_transport,
  operation,
  status,
  COUNT(*) AS config_count
FROM vertex_telecom_oran_o1_config
GROUP BY target_kind, interface_transport, operation, status
