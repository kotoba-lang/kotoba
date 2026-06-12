-- Iryo DRG P&L daily: per-(date, hospital, dept, DRG, tariff) claim margin aggregates.
MODEL (
  name dev.mv_iryo_drg_pnl_daily,
  kind FULL,
  dialect postgres,
  description 'Per (date, hospital, dept, DRG, tariff): claim count, gross/cost/margin points for submitted/paid.',
  grain [created_date, hospital_slug, dept_slug, drg_code, tariff_system],
  tags [iryo, drg, pnl, daily]
);

SELECT
  created_date,
  hospital_slug,
  dept_slug,
  drg_code,
  tariff_system,
  COUNT(*) AS claim_count,
  SUM(COALESCE(package_points, 0)) AS gross_points,
  SUM(COALESCE(cost_estimate, 0)) AS cost_estimate_total,
  SUM(COALESCE(package_points, 0) - COALESCE(cost_estimate, 0)) AS margin_points
FROM vertex_iryo_drg_claim
WHERE status IN ('submitted', 'paid')
GROUP BY created_date, hospital_slug, dept_slug, drg_code, tariff_system
