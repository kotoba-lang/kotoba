-- Handotai subscription tier counts: subscription counts per status and tier.
MODEL (
  name dev.mv_handotai_subscription_tier_counts,
  kind FULL,
  dialect postgres,
  description 'Per (status, tier): subscription count from vertex_handotai_subscription.',
  grain [status, tier],
  tags [handotai, subscription, tier]
);

SELECT
  status,
  tier,
  COUNT(*) AS subscription_count
FROM vertex_handotai_subscription
GROUP BY status, tier
