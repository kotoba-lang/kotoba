-- SQLMesh audit: mv_kyber_tenant_usage_summary invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_kyber_usage_totals_nonnegative,
  model dev.mv_kyber_tenant_usage_summary,
  dialect postgres,
  description 'All meter usage totals must be >= 0 (cumulative deltas should not go negative).'
);
SELECT *
FROM dev.mv_kyber_tenant_usage_summary
WHERE xrpc_requests_total < 0
   OR rw_rows_total < 0
   OR llm_tokens_total < 0
   OR zeebe_instances_total < 0
   OR pds_bytes_total < 0;

---

AUDIT (
  name assert_kyber_tenant_id_present,
  model dev.mv_kyber_tenant_usage_summary,
  dialect postgres,
  description 'tenant_id must not be NULL (PK from billing tenant table).'
);
SELECT *
FROM dev.mv_kyber_tenant_usage_summary
WHERE tenant_id IS NULL;
