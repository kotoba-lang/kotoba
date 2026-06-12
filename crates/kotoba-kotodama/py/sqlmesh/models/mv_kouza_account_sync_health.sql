-- Kouza account sync health: sync run counts and failure rates per account-connection.
MODEL (
  name dev.mv_kouza_account_sync_health,
  kind FULL,
  dialect postgres,
  description 'Per (owner_did, connection_did): sync run count, failed run count, and latest run timestamps.',
  grain [owner_did, connection_did],
  tags [kouza, account, sync, health]
);

SELECT
  owner_did,
  connection_did,
  COUNT(*) AS sync_run_count,
  SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_run_count,
  MAX(started_at) AS latest_started_at,
  MAX(finished_at) AS latest_finished_at
FROM vertex_atrecord_kouza_sync_run
GROUP BY owner_did, connection_did
