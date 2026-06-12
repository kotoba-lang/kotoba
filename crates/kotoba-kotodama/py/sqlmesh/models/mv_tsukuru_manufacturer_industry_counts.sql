-- Tsukuru manufacturer industry counts: manufacturer count per industry, risk tier, and onboarding status.
MODEL (
  name dev.mv_tsukuru_manufacturer_industry_counts,
  kind FULL,
  dialect postgres,
  description 'Per (industry_code, risk_tier, onboarding_status): manufacturer count.',
  grain [industry_code, risk_tier, onboarding_status],
  tags [tsukuru, manufacturer, industry, risk]
);

SELECT
  industry_code,
  risk_tier,
  onboarding_status,
  COUNT(*) AS cnt
FROM vertex_tsukuru_manufacturer
GROUP BY industry_code, risk_tier, onboarding_status
