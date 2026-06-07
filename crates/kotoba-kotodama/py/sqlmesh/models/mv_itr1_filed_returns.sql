-- ITR-1 filed returns: filed and revised income tax returns.
MODEL (
  name dev.mv_itr1_filed_returns,
  kind FULL,
  dialect postgres,
  description 'Filed and revised ITR-1 returns with tax and income summary.',
  grain [vertex_id],
  tags [itr1, india, tax, compliance]
);

SELECT
  taxpayer_pan_hash,
  assessment_year,
  vertex_id,
  status,
  ack_number,
  filed_via,
  total_income_inr_paise,
  total_tax_inr_paise,
  refund_inr_paise,
  tax_payable_inr_paise,
  filed_at
FROM vertex_itr1_return
WHERE status IN ('filed', 'revised')
