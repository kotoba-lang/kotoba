-- Resource flow anomaly review latest: per-anomaly latest review observation.
MODEL (
  name dev.mv_resource_flow_anomaly_review_latest,
  kind FULL,
  dialect postgres,
  description 'Per anomaly_id: latest_observed_at and review_count from vertex_resource_flow_anomaly_review.',
  grain [anomaly_id],
  tags [resource_flow, anomaly, review]
);

SELECT
  anomaly_id,
  MAX(observed_at) AS latest_observed_at,
  COUNT(*) AS review_count
FROM vertex_resource_flow_anomaly_review
GROUP BY anomaly_id
