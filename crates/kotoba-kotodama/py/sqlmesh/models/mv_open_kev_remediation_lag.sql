-- Open KEV remediation lag: active KEV catalog entries per maturity and product category.
MODEL (
  name dev.mv_open_kev_remediation_lag,
  kind FULL,
  dialect postgres,
  description 'Per (exploitation_maturity, product_category): active KEV entry count and latest added.',
  grain [exploitation_maturity, product_category],
  tags [open_kev, remediation, vuln]
);

SELECT
  exploitation_maturity,
  product_category,
  COUNT(*) AS entry_count,
  MAX(added_at) AS latest_added_at
FROM vertex_open_kev_catalog
WHERE status = 'active'
GROUP BY exploitation_maturity, product_category
