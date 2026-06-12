-- Audits for mv_shosha_pnl_daily (ADR-2605080500)

AUDIT (
  name assert_pnl_trade_count_positive,
  model dev.mv_shosha_pnl_daily
)
SELECT *
FROM dev.mv_shosha_pnl_daily
WHERE trade_count <= 0;

AUDIT (
  name assert_pnl_total_equals_sum,
  model dev.mv_shosha_pnl_daily
)
SELECT *
FROM dev.mv_shosha_pnl_daily
WHERE ABS(total_usd - (realized_usd + unrealized_usd)) > 0.01;
