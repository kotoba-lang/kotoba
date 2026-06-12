-- Organizer item status counts: item counts and total bytes per (org, vault, status).
MODEL (
  name dev.mv_organizer_item_status_counts,
  kind FULL,
  dialect postgres,
  description 'Per (org_id, vault_did, status): item count and total bytes.',
  grain [org_id, vault_did, status],
  tags [organizer, item, status]
);

SELECT
  org_id,
  vault_did,
  status,
  COUNT(*)::BIGINT AS item_count,
  SUM(size_bytes) AS total_bytes
FROM vertex_organizer_item
GROUP BY org_id, vault_did, status
