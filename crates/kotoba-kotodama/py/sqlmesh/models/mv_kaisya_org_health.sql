-- Kaisya org health: 24-hour rolling org snapshot health metrics.
MODEL (
  name dev.mv_kaisya_org_health,
  kind FULL,
  dialect postgres,
  description 'Aggregate org snapshot metrics over the last 24 hours: omega/eta/u_total/separation_delta + action totals.',
  grain [],
  tags [kaisya, org, health, snapshot]
);

SELECT
  COUNT(*) AS snapshot_count,
  AVG(omega) AS avg_omega,
  MIN(omega) AS min_omega,
  MAX(omega) AS max_omega,
  AVG(eta_value) AS avg_eta,
  AVG(u_total) AS avg_u_total,
  AVG(separation_delta) FILTER (WHERE separation_delta IS NOT NULL) AS avg_separation_delta,
  SUM(actions_executed) AS total_actions,
  SUM(tasks_created) AS total_tasks_created,
  MAX(snapshot_at) AS latest_at
FROM vertex_kaisya_org_snapshot
WHERE snapshot_at >= NOW() - INTERVAL '24 hours'
