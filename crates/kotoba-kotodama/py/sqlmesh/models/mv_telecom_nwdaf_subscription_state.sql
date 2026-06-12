-- Telecom NWDAF subscription state: NWDAF analytics subscriptions per (analytics_id, target, status).
MODEL (
  name dev.mv_telecom_nwdaf_subscription_state,
  kind FULL,
  dialect postgres,
  description 'Per (analytics_id, target_of_analytics_kind, status): NWDAF subscription count.',
  grain [analytics_id, target_of_analytics_kind, status],
  tags [telecom, nwdaf, subscription]
);

SELECT
  analytics_id,
  target_of_analytics_kind,
  status,
  COUNT(*) AS subscription_count
FROM vertex_telecom_nwdaf_subscription
GROUP BY analytics_id, target_of_analytics_kind, status
