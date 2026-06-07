-- Open GS1 by category: active GTIN counts per product category and country.
MODEL (
  name dev.mv_open_gs1_by_category,
  kind FULL,
  dialect postgres,
  description 'Per (product_category, country_of_origin): active GTIN count and latest registration.',
  grain [product_category, country_of_origin],
  tags [open_gs1, gtin, category]
);

SELECT
  product_category,
  country_of_origin,
  COUNT(*) AS gtin_count,
  MAX(registered_at) AS latest_registered_at
FROM vertex_open_gs1_gtin
WHERE status = 'active'
GROUP BY product_category, country_of_origin
