-- Oshinobi active subscriptions by creator: per-creator active subscriber count and last gross.
MODEL (
  name dev.mv_oshinobi_active_subscriptions_by_creator,
  kind FULL,
  dialect postgres,
  description 'Per creator_did: active subscriber count and last_period_gross_cents from active subscriptions.',
  grain [creator_did],
  tags [oshinobi, subscription, active, creator]
);

SELECT
  creator_did,
  COUNT(*) AS active_subscriber_count,
  SUM(last_charge_cents) AS last_period_gross_cents
FROM vertex_oshinobi_subscription
WHERE status = 'active'
GROUP BY creator_did
