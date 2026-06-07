-- Resource flow anomaly recent: per-(severity, flow_class, source) anomaly counts.
MODEL (
  name dev.mv_resource_flow_anomaly_recent,
  kind FULL,
  dialect postgres,
  description 'Per (severity, flow_class, source_did): anomaly count from vertex_resource_flow_anomaly.',
  grain [severity, flow_class, source_did],
  tags [resource_flow, anomaly]
);

SELECT
  severity,
  flow_class,
  source_did,
  COUNT(*) AS anomaly_count
FROM vertex_resource_flow_anomaly
GROUP BY severity, flow_class, source_did
