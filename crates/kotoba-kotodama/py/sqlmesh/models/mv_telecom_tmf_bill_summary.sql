-- Telecom TMF bill summary: TMF customer bills ordered by period_end.
MODEL (
  name dev.mv_telecom_tmf_bill_summary,
  kind FULL,
  dialect postgres,
  description 'TMF customer bill: account, period, currency, amount, due, status ordered by period_end DESC.',
  grain [account_id, period_start, period_end],
  tags [telecom, tmf, bill, summary]
);

SELECT
  account_id,
  period_start,
  period_end,
  currency,
  total_amount,
  due_at,
  status,
  org_id
FROM vertex_telecom_tmf_customer_bill
ORDER BY period_end DESC
