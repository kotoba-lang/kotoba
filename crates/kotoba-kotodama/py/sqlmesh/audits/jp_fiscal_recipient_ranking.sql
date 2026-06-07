-- SQLMesh audit: mv_jp_fiscal_recipient_ranking invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_jp_fiscal_recipient_amount_nonnegative,
  model dev.mv_jp_fiscal_recipient_ranking,
  dialect postgres,
  description 'total_amount_jpy must be >= 0 (recipient flow amounts are non-negative).'
);
SELECT *
FROM dev.mv_jp_fiscal_recipient_ranking
WHERE total_amount_jpy < 0;

---

AUDIT (
  name assert_jp_fiscal_recipient_flow_count_positive,
  model dev.mv_jp_fiscal_recipient_ranking,
  dialect postgres,
  description 'flow_count must be > 0; recipient_id NOT NULL (filtered by WHERE clause).'
);
SELECT *
FROM dev.mv_jp_fiscal_recipient_ranking
WHERE flow_count <= 0
   OR recipient_id IS NULL;
