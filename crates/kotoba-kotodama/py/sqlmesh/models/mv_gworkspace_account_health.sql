-- Gworkspace account health: union of all 9 Google Workspace service account tables for sync health.
MODEL (
  name dev.mv_gworkspace_account_health,
  kind FULL,
  dialect postgres,
  description 'Per (service, account_did): email, status, and last sync across all Workspace services.',
  grain [service, account_did],
  tags [gworkspace, account, health, sync]
);

SELECT 'gmail' AS service, account_did, email, status, last_sync_at FROM vertex_gmail_account
UNION ALL SELECT 'calendar', account_did, email, status, last_sync_at FROM vertex_gcal_account
UNION ALL SELECT 'drive', account_did, email, status, last_sync_at FROM vertex_gdrive_account
UNION ALL SELECT 'contacts', account_did, email, status, last_sync_at FROM vertex_gcontacts_account
UNION ALL SELECT 'tasks', account_did, email, status, last_sync_at FROM vertex_gtasks_account
UNION ALL SELECT 'docs', account_did, email, status, last_sync_at FROM vertex_gdocs_account
UNION ALL SELECT 'sheets', account_did, email, status, last_sync_at FROM vertex_gsheets_account
UNION ALL SELECT 'slides', account_did, email, status, last_sync_at FROM vertex_gslides_account
UNION ALL SELECT 'meet', account_did, email, status, last_sync_at FROM vertex_gmeet_account
