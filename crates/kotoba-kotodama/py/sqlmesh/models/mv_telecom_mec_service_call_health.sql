-- Telecom MEC service call health: per-(EAS, method, status) call latency and bytes.
MODEL (
  name dev.mv_telecom_mec_service_call_health,
  kind FULL,
  dialect postgres,
  description 'Per (eas_vid, method_kind, status_code): call count, avg latency, total in/out bytes.',
  grain [eas_vid, method_kind, status_code],
  tags [telecom, mec, service_call, health]
);

SELECT
  eas_vid,
  method_kind,
  status_code,
  COUNT(*) AS call_count,
  AVG(latency_ms) AS avg_latency_ms,
  SUM(payload_in_bytes) AS total_in_bytes,
  SUM(payload_out_bytes) AS total_out_bytes
FROM vertex_telecom_mec_service_call
GROUP BY eas_vid, method_kind, status_code
