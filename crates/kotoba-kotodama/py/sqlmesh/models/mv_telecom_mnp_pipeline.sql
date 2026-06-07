-- Telecom MNP pipeline: number portability request counts per direction/status.
MODEL (
  name dev.mv_telecom_mnp_pipeline,
  kind FULL,
  dialect postgres,
  description 'Per (direction, status): MNP request count from vertex_telecom_mnp_request.',
  grain [direction, status],
  tags [telecom, mnp, pipeline]
);

SELECT
  direction,
  status,
  COUNT(*) AS request_count
FROM vertex_telecom_mnp_request
GROUP BY direction, status
