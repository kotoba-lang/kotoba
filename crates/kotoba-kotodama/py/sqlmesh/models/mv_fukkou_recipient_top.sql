-- Fukkou recipient top: recipient organizations with known received totals.
MODEL (
  name dev.mv_fukkou_recipient_top,
  kind FULL,
  dialect postgres,
  description 'Fukkou recipient orgs with non-null total_received_jpy for ranking.',
  grain [org_id],
  tags [fukkou, recipient, ranking]
);

SELECT
  org_id,
  name,
  kind,
  status,
  total_received_jpy,
  flows_received
FROM vertex_fukkou_recipient_org
WHERE total_received_jpy IS NOT NULL
