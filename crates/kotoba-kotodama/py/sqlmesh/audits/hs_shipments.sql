-- SQLMesh audit: mv_open_hs_shipments_by_code invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_hs_shipments_value_nonnegative,
  model dev.mv_open_hs_shipments_by_code,
  dialect postgres,
  description 'total_value_usd must be >= 0.'
);
SELECT *
FROM dev.mv_open_hs_shipments_by_code
WHERE total_value_usd < 0;

---

AUDIT (
  name assert_hs_shipments_avg_confidence_bounded,
  model dev.mv_open_hs_shipments_by_code,
  dialect postgres,
  description 'avg_confidence must be in [0, 1] when present.'
);
SELECT *
FROM dev.mv_open_hs_shipments_by_code
WHERE avg_confidence IS NOT NULL
  AND (avg_confidence < 0 OR avg_confidence > 1);
