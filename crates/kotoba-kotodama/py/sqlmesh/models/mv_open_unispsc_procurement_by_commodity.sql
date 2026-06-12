-- Open UNSPSC procurement by commodity: spend summary per commodity code and currency.
MODEL (
  name dev.mv_open_unispsc_procurement_by_commodity,
  kind FULL,
  dialect postgres,
  description 'Per (commodity_code, currency): procurement count, total spend, CAB flag, latest submitted.',
  grain [commodity_code, currency],
  tags [open_unspsc, procurement, commodity, spend]
);

SELECT
  commodity_code,
  currency,
  COUNT(*) AS procurement_count,
  SUM(total_amount) AS total_spend,
  BOOL_OR(require_cab) AS any_cab_approval,
  MAX(submitted_at) AS latest_submitted_at
FROM vertex_open_unispsc_procurement
WHERE status IN ('submitted', 'approved', 'settled')
GROUP BY commodity_code, currency
