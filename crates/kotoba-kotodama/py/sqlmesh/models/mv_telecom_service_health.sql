-- Telecom service health: service counts and SLA breach counts per service type/plan/status.
MODEL (
  name dev.mv_telecom_service_health,
  kind FULL,
  dialect postgres,
  description 'Per (service_type, plan_id, status): service count and open SLA breaches.',
  grain [service_type, plan_id, status],
  tags [telecom, service, health, sla]
);

SELECT
  s.service_type,
  s.plan_id,
  s.status,
  COUNT(DISTINCT s.vertex_id) AS service_count,
  COUNT(b.vertex_id) AS open_breaches
FROM vertex_telecom_service s
LEFT JOIN vertex_telecom_sla_breach b
  ON b.service_vid = s.vertex_id AND b.status = 'open'
GROUP BY s.service_type, s.plan_id, s.status
