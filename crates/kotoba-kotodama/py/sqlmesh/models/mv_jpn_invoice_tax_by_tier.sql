-- JPN invoice tax by tier: accepted corporate tax filings aggregated by company size and fiscal year.
MODEL (
  name dev.mv_jpn_invoice_tax_by_tier,
  kind FULL,
  dialect postgres,
  description 'Per (size_tier, fiscal_year): filing count, total tax payable, and latest filed for accepted filings.',
  grain [size_tier, fiscal_year],
  tags [jpn, invoice, corporate_tax, tier]
);

SELECT
  size_tier,
  fiscal_year,
  COUNT(*) AS filing_count,
  SUM(tax_payable) AS total_tax_payable,
  MAX(filed_at) AS latest_filed
FROM vertex_jpn_invoice_corporate_tax
WHERE status = 'accepted'
GROUP BY size_tier, fiscal_year
