-- GSTR-3B filed returns: filed and amended GST returns.
MODEL (
  name dev.mv_gstr3b_filed_returns,
  kind FULL,
  dialect postgres,
  description 'Filed and amended GSTR-3B returns with tax summary.',
  grain [vertex_id],
  tags [gstr, india, gst, tax, compliance]
);

SELECT
  gstin_hash,
  tax_period,
  vertex_id,
  status,
  arn,
  filed_via,
  total_outward_tax_inr_paise,
  total_inward_itc_inr_paise,
  total_net_tax_inr_paise,
  filed_at
FROM vertex_gstr3b_return
WHERE status IN ('filed', 'amended')
