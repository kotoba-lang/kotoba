-- Telecom WLAN settlement balance: per-(partner, currency) WLAN roaming financial aggregates.
MODEL (
  name dev.mv_telecom_wlan_settlement_balance,
  kind FULL,
  dialect postgres,
  description 'Per (partner_org_id, currency): receivable, payable, net balance, invoice count for issued/settled.',
  grain [partner_org_id, currency],
  tags [telecom, wlan, settlement]
);

SELECT
  partner_org_id,
  currency,
  SUM(receivable_amount) AS total_receivable,
  SUM(payable_amount) AS total_payable,
  SUM(net_amount) AS net_balance,
  COUNT(*) AS invoice_count
FROM vertex_telecom_wlan_roaming_invoice
WHERE status IN ('issued', 'settled')
GROUP BY partner_org_id, currency
