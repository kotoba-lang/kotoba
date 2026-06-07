-- Telecom roaming settlement balance: per-(partner, currency) roaming financial aggregates.
MODEL (
  name dev.mv_telecom_roaming_settlement_balance,
  kind FULL,
  dialect postgres,
  description 'Per (partner_vid, currency): receivable, payable, net balance, invoice count for issued/settled invoices.',
  grain [partner_vid, currency],
  tags [telecom, roaming, settlement]
);

SELECT
  partner_vid,
  currency,
  SUM(receivable_amount) AS total_receivable,
  SUM(payable_amount) AS total_payable,
  SUM(net_amount) AS net_balance,
  COUNT(*) AS invoice_count
FROM vertex_telecom_roaming_invoice
WHERE status IN ('issued', 'settled')
GROUP BY partner_vid, currency
