-- JP fiscal recipient ranking: per-recipient flow count and total amount aggregates.
MODEL (
  name dev.mv_jp_fiscal_recipient_ranking,
  kind FULL,
  dialect postgres,
  description 'Per (fiscal_year, recipient_id, recipient_name, recipient_kind, corporate_number): flow count and total JPY.',
  grain [fiscal_year, recipient_id],
  tags [jp_fiscal, recipient, ranking]
);

SELECT
  fiscal_year,
  recipient_id,
  recipient_name,
  recipient_kind,
  corporate_number,
  COUNT(*) AS flow_count,
  SUM(amount_jpy) AS total_amount_jpy
FROM edge_jp_fiscal_flow
WHERE recipient_id IS NOT NULL
GROUP BY fiscal_year, recipient_id, recipient_name, recipient_kind, corporate_number
