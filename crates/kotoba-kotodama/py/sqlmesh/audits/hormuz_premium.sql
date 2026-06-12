-- SQLMesh audit: mv_open_hormuz_premium_by_flag invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_hormuz_premium_bps_nonnegative,
  model dev.mv_open_hormuz_premium_by_flag,
  dialect postgres,
  description 'avg_premium_bps must be >= 0 (insurance premium basis points are non-negative).'
);
SELECT *
FROM dev.mv_open_hormuz_premium_by_flag
WHERE avg_premium_bps < 0;

---

AUDIT (
  name assert_hormuz_premium_quote_count_positive,
  model dev.mv_open_hormuz_premium_by_flag,
  dialect postgres,
  description 'quote_count must be > 0 (group rows imply at least one active quote).'
);
SELECT *
FROM dev.mv_open_hormuz_premium_by_flag
WHERE quote_count <= 0;
