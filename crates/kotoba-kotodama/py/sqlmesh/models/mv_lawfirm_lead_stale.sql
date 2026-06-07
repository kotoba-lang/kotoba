-- Lawfirm lead stale: leads with no recent touch in upstream stages.
MODEL (
  name dev.mv_lawfirm_lead_stale,
  kind FULL,
  dialect postgres,
  description 'Per lead in lead/contacted/meeting_requested with last_touch_at older than 5 days.',
  grain [lead_id],
  tags [lawfirm, lead, stale, sales]
);

SELECT
  lead_id,
  target_name,
  target_email,
  stage,
  last_touch_at,
  next_action,
  assigned_to_did,
  conversion_value_usd
FROM vertex_lawfirm_lead
WHERE stage IN ('lead', 'contacted', 'meeting_requested')
  AND last_touch_at IS NOT NULL
  AND last_touch_at < CAST(now() - INTERVAL '5 days' AS VARCHAR)
