-- Yadoya flow currency by chain period: reservation revenue and refund event counts.
MODEL (
  name dev.mv_yadoya_flow_currency_by_chain_period,
  kind FULL,
  dialect postgres,
  description 'Per (counterparty, period, currency, bucket): event count for reservation_revenue/cancellation_refund.',
  grain [counterparty_did, fiscal_period, currency, amount_bucket],
  tags [yadoya, flow, currency, chain]
);

SELECT
  COALESCE(counterparty_did, 'independent') AS counterparty_did,
  fiscal_period,
  currency,
  amount_bucket,
  COUNT(*) AS event_count
FROM vertex_yadoya_flow_event
WHERE flow_kind IN ('reservation_revenue', 'cancellation_refund')
GROUP BY COALESCE(counterparty_did, 'independent'), fiscal_period, currency, amount_bucket
