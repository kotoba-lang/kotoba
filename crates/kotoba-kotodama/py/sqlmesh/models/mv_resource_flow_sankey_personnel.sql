-- Resource flow Sankey personnel: aggregated personnel headcount flows.
MODEL (
  name dev.mv_resource_flow_sankey_personnel,
  kind FULL,
  dialect postgres,
  description 'Per source/counterparty/period/flow_type/industry: headcount sum and event count.',
  grain [source_did, counterparty_did, fiscal_period, flow_type, industry_code],
  tags [resource_flow, sankey, personnel]
);

SELECT
  source_did,
  COALESCE(counterparty_did, 'independent') AS counterparty_did,
  fiscal_period,
  flow_type,
  industry_code,
  SUM(headcount_delta) AS headcount_sum,
  COUNT(*) AS event_count
FROM vertex_resource_flow_personnel
GROUP BY source_did, COALESCE(counterparty_did, 'independent'),
         fiscal_period, flow_type, industry_code
