-- Telecom subscriber state: subscriber counts per plan/KYC/status.
MODEL (
  name dev.mv_telecom_subscriber_state,
  kind FULL,
  dialect postgres,
  description 'Per (plan_id, kyc_status, status): subscriber count from vertex_telecom_subscriber.',
  grain [plan_id, kyc_status, status],
  tags [telecom, subscriber, state]
);

SELECT
  plan_id,
  kyc_status,
  status,
  COUNT(*) AS subscriber_count
FROM vertex_telecom_subscriber
GROUP BY plan_id, kyc_status, status
