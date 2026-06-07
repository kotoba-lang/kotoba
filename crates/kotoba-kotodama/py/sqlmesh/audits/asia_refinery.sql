-- SQLMesh audit: mv_open_asia_refinery_throughput invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_asia_refinery_total_tonnes_nonnegative,
  model dev.mv_open_asia_refinery_throughput,
  dialect postgres,
  description 'total_tonnes must be >= 0 (received volumes are non-negative).'
);
SELECT *
FROM dev.mv_open_asia_refinery_throughput
WHERE total_tonnes < 0;

---

AUDIT (
  name assert_asia_refinery_receipt_count_positive,
  model dev.mv_open_asia_refinery_throughput,
  dialect postgres,
  description 'receipt_count must be > 0 (group rows imply at least one received receipt).'
);
SELECT *
FROM dev.mv_open_asia_refinery_throughput
WHERE receipt_count <= 0;
