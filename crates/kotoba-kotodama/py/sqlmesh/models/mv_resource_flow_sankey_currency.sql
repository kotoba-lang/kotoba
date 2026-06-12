-- Resource flow Sankey currency: aggregated currency flows for Sankey visualization.
MODEL (
  name dev.mv_resource_flow_sankey_currency,
  kind FULL,
  dialect postgres,
  description 'Per source/counterparty/period/flow_type/currency/industry/bucket: amount sum and event count.',
  grain [source_did, counterparty_did, fiscal_period, flow_type, currency, industry_code, amount_bucket],
  tags [resource_flow, sankey, currency]
);

SELECT
  source_did,
  COALESCE(counterparty_did, 'independent') AS counterparty_did,
  fiscal_period,
  flow_type,
  currency,
  industry_code,
  amount_bucket,
  SUM(COALESCE(amount, 0)) AS amount_sum,
  COUNT(*) AS event_count
FROM vertex_resource_flow_currency
GROUP BY source_did, COALESCE(counterparty_did, 'independent'),
         fiscal_period, flow_type, currency, industry_code, amount_bucket
