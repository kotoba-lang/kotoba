-- Telecom active sessions: PDU session counts per slice/DNN/type.
MODEL (
  name dev.mv_telecom_active_sessions,
  kind FULL,
  dialect postgres,
  description 'Per (snssai, dnn, session_type): active PDU session count.',
  grain [snssai, dnn, session_type],
  tags [telecom, 5g, pdu, session, active]
);

SELECT
  snssai,
  dnn,
  session_type,
  COUNT(*) AS active_session_count
FROM vertex_telecom_pdu_session
WHERE status = 'active'
GROUP BY snssai, dnn, session_type
