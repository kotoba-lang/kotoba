-- Kyber tenant usage summary: per-tenant cumulative usage across all meter types.
MODEL (
  name dev.mv_kyber_tenant_usage_summary,
  kind FULL,
  dialect postgres,
  description 'Per tenant: plan, status, limits, and cumulative usage across xrpc/rw/llm/zeebe/pds meters.',
  grain [tenant_id],
  tags [kyber, billing, tenant, usage]
);

SELECT
  t.tenant_id,
  t.org_did,
  t.plan_id,
  t.status AS tenant_status,
  t.max_users,
  t.max_monthly_txns,
  COALESCE(SUM(u.delta_count) FILTER (WHERE u.meter_type = 'xrpc_request'), 0) AS xrpc_requests_total,
  COALESCE(SUM(u.delta_count) FILTER (WHERE u.meter_type = 'rw_row'), 0) AS rw_rows_total,
  COALESCE(SUM(u.delta_count) FILTER (WHERE u.meter_type = 'llm_token'), 0) AS llm_tokens_total,
  COALESCE(SUM(u.delta_count) FILTER (WHERE u.meter_type = 'zeebe_instance'), 0) AS zeebe_instances_total,
  COALESCE(SUM(u.delta_count) FILTER (WHERE u.meter_type = 'pds_byte'), 0) AS pds_bytes_total
FROM vertex_kyber_billing_tenant t
LEFT JOIN vertex_kyber_usage_meter u ON t.tenant_id = u.tenant_id
GROUP BY t.tenant_id, t.org_did, t.plan_id, t.status, t.max_users, t.max_monthly_txns
