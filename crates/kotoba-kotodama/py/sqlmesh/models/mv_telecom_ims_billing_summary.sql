-- Telecom IMS billing summary: per-subscriber IMS billing event aggregates.
MODEL (
  name dev.mv_telecom_ims_billing_summary,
  kind FULL,
  dialect postgres,
  description 'Per (subscriber_vid, currency, charging_method): total amount and event count.',
  grain [subscriber_vid, currency, charging_method],
  tags [telecom, ims, billing, summary]
);

SELECT
  subscriber_vid,
  currency,
  charging_method,
  SUM(amount) AS total_amount,
  COUNT(*) AS event_count
FROM vertex_telecom_ims_billing_event
GROUP BY subscriber_vid, currency, charging_method
