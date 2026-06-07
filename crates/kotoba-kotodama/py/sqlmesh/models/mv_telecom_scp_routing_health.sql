-- Telecom SCP routing health: SCP route request counts and latency aggregates.
MODEL (
  name dev.mv_telecom_scp_routing_health,
  kind FULL,
  dialect postgres,
  description 'Per (target_service_name, routing_mode, status_code): request count and avg latency_ms.',
  grain [target_service_name, routing_mode, status_code],
  tags [telecom, 5g, scp, routing]
);

SELECT
  target_service_name,
  routing_mode,
  status_code,
  COUNT(*) AS request_count,
  AVG(latency_ms) AS avg_latency_ms
FROM vertex_telecom_scp_route
GROUP BY target_service_name, routing_mode, status_code
