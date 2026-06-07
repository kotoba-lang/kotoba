-- SQLMesh audit: mv_open_sales_stage_velocity invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_sales_velocity_outcomes_le_total,
  model dev.mv_open_sales_stage_velocity,
  dialect postgres,
  description 'won_count + lost_count must not exceed opp_count (other status values allowed).'
);
SELECT *
FROM dev.mv_open_sales_stage_velocity
WHERE won_count + lost_count > opp_count;

---

AUDIT (
  name assert_sales_velocity_avg_deal_nonnegative,
  model dev.mv_open_sales_stage_velocity,
  dialect postgres,
  description 'avg_deal_size_usd must be >= 0.'
);
SELECT *
FROM dev.mv_open_sales_stage_velocity
WHERE avg_deal_size_usd < 0;
