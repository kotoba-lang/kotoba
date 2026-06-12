-- JPN JPO applications by IPC: patent application counts per IPC class and status.
MODEL (
  name dev.mv_jpn_jpo_app_by_ipc,
  kind FULL,
  dialect postgres,
  description 'Per (ipc_classes, status): application count and latest filing for filed/pending/granted apps.',
  grain [ipc_classes, status],
  tags [jpn, jpo, patent, ipc]
);

SELECT
  ipc_classes,
  status,
  COUNT(*) AS app_count,
  MAX(filing_date) AS latest_filing
FROM vertex_jpn_jpo_application
WHERE status IN ('filed', 'pending', 'granted')
GROUP BY ipc_classes, status
