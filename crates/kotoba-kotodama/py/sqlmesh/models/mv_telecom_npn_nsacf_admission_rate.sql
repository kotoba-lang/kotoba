-- Telecom NPN NSACF admission rate: per-(slice, request_kind, decision) admission counts.
MODEL (
  name dev.mv_telecom_npn_nsacf_admission_rate,
  kind FULL,
  dialect postgres,
  description 'Per (snssai, request_kind, decision): NSACF decision count.',
  grain [snssai, request_kind, decision],
  tags [telecom, npn, nsacf, admission]
);

SELECT
  snssai,
  request_kind,
  decision,
  COUNT(*) AS decision_count
FROM vertex_telecom_npn_nsacf_decision
GROUP BY snssai, request_kind, decision
