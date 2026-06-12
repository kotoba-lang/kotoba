-- Telecom LI warrant state: lawful intercept warrant counts per jurisdiction/kind/scope/status.
MODEL (
  name dev.mv_telecom_li_warrant_state,
  kind FULL,
  dialect postgres,
  description 'Per (jurisdiction, warrant_kind, intercept_scope, status): warrant count.',
  grain [jurisdiction, warrant_kind, intercept_scope, status],
  tags [telecom, li, warrant]
);

SELECT
  jurisdiction,
  warrant_kind,
  intercept_scope,
  status,
  COUNT(*) AS warrant_count
FROM vertex_telecom_li_warrant
GROUP BY jurisdiction, warrant_kind, intercept_scope, status
