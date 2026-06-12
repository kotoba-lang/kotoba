-- Resource flow Sankey service: aggregated service flows for Sankey visualization.
MODEL (
  name dev.mv_resource_flow_sankey_service,
  kind FULL,
  dialect postgres,
  description 'Per source/counterparty/period/service_class/unit/industry: total count, revenue sum, event count.',
  grain [source_did, counterparty_did, fiscal_period, service_class, service_unit, industry_code],
  tags [resource_flow, sankey, service]
);

SELECT
  source_did,
  COALESCE(counterparty_did, 'independent') AS counterparty_did,
  fiscal_period,
  service_class,
  service_unit,
  industry_code,
  SUM(service_count) AS total_count,
  SUM(COALESCE(revenue, 0)) AS revenue_sum,
  COUNT(*) AS event_count
FROM vertex_resource_flow_service
GROUP BY source_did, COALESCE(counterparty_did, 'independent'),
         fiscal_period, service_class, service_unit, industry_code
