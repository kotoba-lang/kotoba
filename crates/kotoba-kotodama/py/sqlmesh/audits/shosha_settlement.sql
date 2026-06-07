-- Audits for mv_shosha_settled_pnl_daily and mv_shosha_approval_summary (ADR-2605080500)

AUDIT (
  name assert_settled_count_positive,
  model dev.mv_shosha_settled_pnl_daily
)
SELECT *
FROM dev.mv_shosha_settled_pnl_daily
WHERE settled_count <= 0;

AUDIT (
  name assert_settled_notional_nonneg,
  model dev.mv_shosha_settled_pnl_daily
)
SELECT *
FROM dev.mv_shosha_settled_pnl_daily
WHERE settled_notional_usd < 0;

AUDIT (
  name assert_approval_decision_not_null,
  model dev.mv_shosha_approval_summary
)
SELECT *
FROM dev.mv_shosha_approval_summary
WHERE decision IS NULL;

AUDIT (
  name assert_approval_decision_count_positive,
  model dev.mv_shosha_approval_summary
)
SELECT *
FROM dev.mv_shosha_approval_summary
WHERE decision_count <= 0;
