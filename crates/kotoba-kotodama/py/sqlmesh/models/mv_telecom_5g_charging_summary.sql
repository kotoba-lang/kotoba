-- Telecom 5G charging summary: per-subscriber charging totals.
MODEL (
  name dev.mv_telecom_5g_charging_summary,
  kind FULL,
  dialect postgres,
  description 'Per (subscriber_vid, currency, charging_method): total amount, units, record count.',
  grain [subscriber_vid, currency, charging_method],
  tags [telecom, 5g, charging]
);

SELECT
  subscriber_vid,
  currency,
  charging_method,
  SUM(amount) AS total_amount,
  SUM(units) AS total_units,
  COUNT(*) AS record_count
FROM vertex_telecom_charging_record
GROUP BY subscriber_vid, currency, charging_method
