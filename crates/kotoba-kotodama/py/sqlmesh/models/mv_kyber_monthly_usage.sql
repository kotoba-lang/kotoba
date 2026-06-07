-- Kyber monthly usage: per-tenant monthly usage totals by meter type.
MODEL (
  name dev.mv_kyber_monthly_usage,
  kind FULL,
  dialect postgres,
  description 'Per (tenant_id, org_did, meter_type, period_month): summed delta_count.',
  grain [tenant_id, meter_type, period_month],
  tags [kyber, billing, usage, monthly]
);

SELECT
  tenant_id,
  org_did,
  meter_type,
  period_month,
  SUM(delta_count) AS total_count
FROM vertex_kyber_usage_meter
GROUP BY tenant_id, org_did, meter_type, period_month
