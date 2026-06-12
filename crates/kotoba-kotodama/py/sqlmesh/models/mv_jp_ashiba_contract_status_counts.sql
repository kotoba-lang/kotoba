-- JP Ashiba contract status counts: rental contract counts and amounts per status.
MODEL (
  name dev.mv_jp_ashiba_contract_status_counts,
  kind FULL,
  dialect postgres,
  description 'Per status: contract count and total amount sum from vertex_jp_ashiba_rental_contract.',
  grain [status],
  tags [jp_ashiba, contract, status]
);

SELECT
  status,
  COUNT(*) AS cnt,
  SUM(COALESCE(total_amount, 0)) AS total_amount_sum
FROM vertex_jp_ashiba_rental_contract
GROUP BY status
