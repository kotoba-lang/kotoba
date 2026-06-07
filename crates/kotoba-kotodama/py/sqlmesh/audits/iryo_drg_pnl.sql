-- SQLMesh audit: mv_iryo_drg_pnl_daily invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_iryo_drg_margin_consistent,
  model dev.mv_iryo_drg_pnl_daily,
  dialect postgres,
  description 'margin_points must equal gross_points - cost_estimate_total.'
);
SELECT *
FROM dev.mv_iryo_drg_pnl_daily
WHERE margin_points <> gross_points - cost_estimate_total;

---

AUDIT (
  name assert_iryo_drg_claim_count_positive,
  model dev.mv_iryo_drg_pnl_daily,
  dialect postgres,
  description 'claim_count must be > 0 (group rows imply at least one claim).'
);
SELECT *
FROM dev.mv_iryo_drg_pnl_daily
WHERE claim_count <= 0;
