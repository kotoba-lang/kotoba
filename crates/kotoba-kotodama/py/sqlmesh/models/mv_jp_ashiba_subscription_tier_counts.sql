-- JP Ashiba subscription tier counts: subscription plan counts and fee totals per tier.
MODEL (
  name dev.mv_jp_ashiba_subscription_tier_counts,
  kind FULL,
  dialect postgres,
  description 'Per (tier, status): subscription count and monthly fee sum from vertex_jp_ashiba_subscription_plan.',
  grain [tier, status],
  tags [jp_ashiba, subscription, tier]
);

SELECT
  tier,
  status,
  COUNT(*) AS cnt,
  SUM(COALESCE(monthly_fee, 0)) AS monthly_fee_sum
FROM vertex_jp_ashiba_subscription_plan
GROUP BY tier, status
