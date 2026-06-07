-- Telecom O-RAN A1 policy state: A1 policy counts per use case/scope/action/status.
MODEL (
  name dev.mv_telecom_oran_a1_policy_state,
  kind FULL,
  dialect postgres,
  description 'Per (use_case, scope_kind, action, status): A1 policy count.',
  grain [use_case, scope_kind, action, status],
  tags [telecom, oran, a1, policy]
);

SELECT
  use_case,
  scope_kind,
  action,
  status,
  COUNT(*) AS policy_count
FROM vertex_telecom_oran_a1_policy
GROUP BY use_case, scope_kind, action, status
