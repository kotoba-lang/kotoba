-- Open SaaS products by category: active SaaS product counts per category and risk score.
MODEL (
  name dev.mv_open_saas_products_by_category,
  kind FULL,
  dialect postgres,
  description 'Per (category, risk_score): active product count, security review flag, latest registered.',
  grain [category, risk_score],
  tags [open_saas, product, category]
);

SELECT
  category,
  risk_score,
  COUNT(*) AS product_count,
  BOOL_OR(require_security_review) AS any_review_required,
  MAX(registered_at) AS latest_registered_at
FROM vertex_open_saas_product
WHERE status = 'active'
GROUP BY category, risk_score
