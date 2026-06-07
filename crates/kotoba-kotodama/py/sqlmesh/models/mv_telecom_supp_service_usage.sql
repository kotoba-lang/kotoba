-- Telecom supplementary service usage: per-(service_type, action) event count.
MODEL (
  name dev.mv_telecom_supp_service_usage,
  kind FULL,
  dialect postgres,
  description 'Per (service_type, action): event count from vertex_telecom_supp_service_event.',
  grain [service_type, action],
  tags [telecom, ims, supplementary_service, usage]
);

SELECT
  service_type,
  action,
  COUNT(*) AS event_count
FROM vertex_telecom_supp_service_event
GROUP BY service_type, action
