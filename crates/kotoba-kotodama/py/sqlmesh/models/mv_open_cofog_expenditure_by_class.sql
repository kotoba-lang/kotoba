-- Open COFOG expenditure by class: confirmed spend per class, year, currency.
MODEL (
  name dev.mv_open_cofog_expenditure_by_class,
  kind FULL,
  dialect postgres,
  description 'Per (cofog_class_code, fiscal_year, currency): confirmed expenditure count, total amount, latest reported.',
  grain [cofog_class_code, fiscal_year, currency],
  tags [open_cofog, expenditure, fiscal, public_finance]
);

SELECT
  cofog_class_code,
  fiscal_year,
  currency,
  COUNT(*) AS expenditure_count,
  SUM(amount) AS total_amount,
  MAX(reported_at) AS latest_reported_at
FROM vertex_open_cofog_expenditure
WHERE status = 'confirmed'
GROUP BY cofog_class_code, fiscal_year, currency
