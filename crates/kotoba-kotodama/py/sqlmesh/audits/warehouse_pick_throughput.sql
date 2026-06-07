-- SQLMesh audit: mv_warehouse_pick_throughput_1h invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_warehouse_pick_count_positive,
  model dev.mv_warehouse_pick_throughput_1h,
  dialect postgres,
  description 'pick_count must be > 0 (group rows imply at least one pick).'
);
SELECT *
FROM dev.mv_warehouse_pick_throughput_1h
WHERE pick_count <= 0;

---

AUDIT (
  name assert_warehouse_picked_qty_nonnegative,
  model dev.mv_warehouse_pick_throughput_1h,
  dialect postgres,
  description 'picked_qty_total must be >= 0 (quantities are non-negative).'
);
SELECT *
FROM dev.mv_warehouse_pick_throughput_1h
WHERE picked_qty_total < 0;

---

AUDIT (
  name assert_warehouse_avg_bins_positive,
  model dev.mv_warehouse_pick_throughput_1h,
  dialect postgres,
  description 'avg_bins_per_pick must be > 0 (every pick draws from >=1 bin).'
);
SELECT *
FROM dev.mv_warehouse_pick_throughput_1h
WHERE avg_bins_per_pick IS NOT NULL
  AND avg_bins_per_pick <= 0;
