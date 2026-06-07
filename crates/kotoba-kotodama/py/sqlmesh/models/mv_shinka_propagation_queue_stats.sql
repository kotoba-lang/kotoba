-- Shinka propagation queue stats: job count per status.
MODEL (
  name dev.mv_shinka_propagation_queue_stats,
  kind FULL,
  dialect postgres,
  description 'Per status: propagation job count from vertex_shinka_propagation_job.',
  grain [status],
  tags [shinka, propagation, queue, status]
);

SELECT
  status,
  COUNT(*) AS cnt
FROM vertex_shinka_propagation_job
GROUP BY status
