-- Lawfirm revenue monthly: per-month revenue aggregates by currency and stream.
MODEL (
  name dev.mv_lawfirm_revenue_monthly,
  kind FULL,
  dialect postgres,
  description 'Per (month, currency, stream): paid amount sum and payment count.',
  grain [month, currency, stream],
  tags [lawfirm, revenue, monthly]
);

SELECT
  SUBSTRING(paid_at, 1, 7) AS month,
  currency,
  COALESCE(stream, 'unknown') AS stream,
  SUM(amount_minor) AS amount_minor_total,
  COUNT(*) AS payment_count
FROM vertex_lawfirm_payment
WHERE paid_at IS NOT NULL
GROUP BY SUBSTRING(paid_at, 1, 7), currency, COALESCE(stream, 'unknown')
