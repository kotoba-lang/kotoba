-- Training run status: training run counts and timestamps per kind/status.
MODEL (
  name dev.mv_training_run_status,
  kind FULL,
  dialect postgres,
  description 'Per (kind, status): training run count and last started_at/ended_at.',
  grain [kind, status],
  tags [training, run, status]
);

SELECT
  kind,
  status,
  COUNT(*) AS run_count,
  MAX(started_at) AS last_started_at,
  MAX(ended_at) AS last_ended_at
FROM vertex_training_run
GROUP BY kind, status
