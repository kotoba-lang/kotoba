-- Yorishiro flyio job status: union of cancellation/app-delete/org-delete job counts.
MODEL (
  name dev.mv_yorishiro_flyio_job_status,
  kind FULL,
  dialect postgres,
  description 'Per (job_kind, action, status): flyio job count and latest_created_at across 3 job kinds.',
  grain [job_kind, action, status],
  tags [yorishiro, flyio, job, status]
);

SELECT 'cancellation' AS job_kind, phase AS action, status, COUNT(*) AS job_count, MAX(created_at) AS latest_created_at
FROM vertex_yorishiroFlyio_cancellationJob
GROUP BY phase, status
UNION ALL
SELECT 'app_delete' AS job_kind, 'deleteApp' AS action, status, COUNT(*) AS job_count, MAX(created_at) AS latest_created_at
FROM vertex_yorishiroFlyio_appDeleteJob
GROUP BY status
UNION ALL
SELECT 'org_delete' AS job_kind, 'deleteOrg' AS action, status, COUNT(*) AS job_count, MAX(created_at) AS latest_created_at
FROM vertex_yorishiroFlyio_orgDeleteJob
GROUP BY status
