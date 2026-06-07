-- Organizer subscription monthly cost: monthly normalized cost per (org, currency, status).
MODEL (
  name dev.mv_organizer_subscription_monthly_cost,
  kind FULL,
  dialect postgres,
  description 'Per (org_id, currency, status): subscription count and monthly cost (yearly/4.33 weekly normalization).',
  grain [org_id, currency, status],
  tags [organizer, subscription, cost]
);

SELECT
  org_id,
  currency,
  status,
  COUNT(*)::BIGINT AS subscription_count,
  SUM(CASE billing_cycle
    WHEN 'yearly' THEN amount / 12
    WHEN 'weekly' THEN amount * 4.33
    ELSE amount
  END) AS monthly_cost
FROM vertex_organizer_subscription_item
GROUP BY org_id, currency, status
