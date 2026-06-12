-- Yorishiro nuro claim flow: claim job → receipt → offer join.
MODEL (
  name dev.mv_yorishiro_nuro_claim_flow,
  kind FULL,
  dialect postgres,
  description 'Per claim job: campaign, status, receipt amount, offer window.',
  grain [job_id],
  tags [yorishiro, nuro, claim, flow]
);

SELECT
  j.job_id,
  j.campaign_code,
  j.status,
  j.created_at,
  r.receipt_number,
  r.submitted_at,
  r.amount_jpy,
  o.title AS offer_title,
  o.window_open,
  o.window_close
FROM vertex_yorishiroNuro_claimJob j
LEFT JOIN vertex_yorishiroNuro_claimReceipt r ON r.job_id = j.job_id
LEFT JOIN vertex_yorishiroNuro_offer o ON o.campaign_code = j.campaign_code
