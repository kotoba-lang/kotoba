-- Telecom auth failure rate: auth event counts per (method, result).
MODEL (
  name dev.mv_telecom_auth_failure_rate,
  kind FULL,
  dialect postgres,
  description 'Per (auth_method, result): auth event count from vertex_telecom_auth_event.',
  grain [auth_method, result],
  tags [telecom, auth, failure_rate]
);

SELECT
  auth_method,
  result,
  COUNT(*) AS event_count
FROM vertex_telecom_auth_event
GROUP BY auth_method, result
