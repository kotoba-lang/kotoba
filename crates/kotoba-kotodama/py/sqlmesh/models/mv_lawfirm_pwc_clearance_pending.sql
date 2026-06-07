-- Lawfirm PwC clearance pending: pending PwC clearance requests with SLA metadata.
MODEL (
  name dev.mv_lawfirm_pwc_clearance_pending,
  kind FULL,
  dialect postgres,
  description 'Pending PwC clearance: matter, client, requested_at, SLA deadline, escalation flag.',
  grain [vertex_id],
  tags [lawfirm, pwc, clearance, pending]
);

SELECT
  vertex_id,
  matter_uri,
  client_name,
  requested_at,
  sla_deadline,
  escalated
FROM vertex_lawfirm_pwc_clearance
WHERE clearance_status = 'pending'
