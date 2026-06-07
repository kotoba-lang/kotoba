-- Telecom O-RAN E2 subscription state: E2 subscription counts per service model/trigger/action/status.
MODEL (
  name dev.mv_telecom_oran_e2_subscription_state,
  kind FULL,
  dialect postgres,
  description 'Per (service_model, event_trigger_kind, action_kind, status): E2 subscription count.',
  grain [service_model, event_trigger_kind, action_kind, status],
  tags [telecom, oran, e2, subscription]
);

SELECT
  service_model,
  event_trigger_kind,
  action_kind,
  status,
  COUNT(*) AS subscription_count
FROM vertex_telecom_oran_e2_subscription
GROUP BY service_model, event_trigger_kind, action_kind, status
