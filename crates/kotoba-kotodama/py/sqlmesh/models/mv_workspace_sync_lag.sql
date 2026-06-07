-- Workspace sync lag: per-(provider, kind, scope) sync job lag and failure metrics.
MODEL (
  name dev.mv_workspace_sync_lag,
  kind FULL,
  dialect postgres,
  description 'Per (provider, source_kind, scope_key): last_ended_at, last_success_at, failed counts (total/today).',
  grain [provider, source_kind, scope_key],
  tags [workspace, sync, lag]
);

SELECT
  provider,
  source_kind,
  scope_key,
  MAX(ended_at) AS last_ended_at,
  MAX(CASE WHEN status = 'ok' THEN ended_at ELSE '' END) AS last_success_at,
  SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_count_total,
  SUM(CASE WHEN status = 'failed' AND SUBSTRING(COALESCE(ended_at, ''), 1, 10) >= SUBSTRING(CAST(NOW() AS VARCHAR), 1, 10) THEN 1 ELSE 0 END) AS failed_count_today
FROM vertex_workspace_sync_job
GROUP BY provider, source_kind, scope_key
