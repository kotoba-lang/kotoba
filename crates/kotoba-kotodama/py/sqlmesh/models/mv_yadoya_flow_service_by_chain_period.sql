-- Yadoya flow service by chain period: per-service-class flow event aggregates.
MODEL (
  name dev.mv_yadoya_flow_service_by_chain_period,
  kind FULL,
  dialect postgres,
  description 'Per (counterparty, period, service_class, service_unit): total service count and event count.',
  grain [counterparty_did, fiscal_period, service_class, service_unit],
  tags [yadoya, flow, service, chain]
);

SELECT
  COALESCE(counterparty_did, 'independent') AS counterparty_did,
  fiscal_period,
  service_class,
  service_unit,
  SUM(service_count) AS total_count,
  COUNT(*) AS event_count
FROM vertex_yadoya_flow_event
WHERE service_class IS NOT NULL
GROUP BY COALESCE(counterparty_did, 'independent'), fiscal_period, service_class, service_unit
