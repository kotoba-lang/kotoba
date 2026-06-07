-- Telecom NFV SDN flow state: SDN flow counts per controller/protocol/action/status.
MODEL (
  name dev.mv_telecom_nfv_sdn_flow_state,
  kind FULL,
  dialect postgres,
  description 'Per (sdn_controller_id, southbound_protocol, action, status): flow count.',
  grain [sdn_controller_id, southbound_protocol, action, status],
  tags [telecom, nfv, sdn, flow]
);

SELECT
  sdn_controller_id,
  southbound_protocol,
  action,
  status,
  COUNT(*) AS flow_count
FROM vertex_telecom_nfv_sdn_flow
GROUP BY sdn_controller_id, southbound_protocol, action, status
