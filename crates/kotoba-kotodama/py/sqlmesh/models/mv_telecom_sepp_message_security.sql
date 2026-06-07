-- Telecom SEPP message security: SEPP message counts and latency per N32 channel/direction/security result.
MODEL (
  name dev.mv_telecom_sepp_message_security,
  kind FULL,
  dialect postgres,
  description 'Per (n32_channel, direction, security_result): message count and avg latency_ms.',
  grain [n32_channel, direction, security_result],
  tags [telecom, 5g, sepp, security]
);

SELECT
  n32_channel,
  direction,
  security_result,
  COUNT(*) AS message_count,
  AVG(latency_ms) AS avg_latency_ms
FROM vertex_telecom_sepp_message
GROUP BY n32_channel, direction, security_result
