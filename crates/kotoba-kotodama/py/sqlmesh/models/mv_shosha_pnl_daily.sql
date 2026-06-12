-- ADR-2605080500: SQLMesh Phase 0 source-of-truth for mv_shosha_pnl_daily
-- Daily realized + unrealized P&L per commodity for the shosha sogo-shosha actor.
-- Source table: vertex_shosha_trade (comply_ok=true trades only).
MODEL (
  name dev.mv_shosha_pnl_daily,
  kind FULL,
  dialect postgres,
  description 'Daily realized + unrealized P&L per commodity for shosha actor.',
  grain [created_date, commodity],
  tags [shosha, pnl, trading, materialized_view, adr_2605080500]
);

SELECT
  created_date,
  commodity,
  SUM(COALESCE(pnl_realized, 0))                                    AS realized_usd,
  SUM(COALESCE(pnl_unrealized, 0))                                  AS unrealized_usd,
  SUM(COALESCE(pnl_realized, 0) + COALESCE(pnl_unrealized, 0))     AS total_usd,
  COUNT(*)                                                           AS trade_count
FROM vertex_shosha_trade
WHERE comply_ok = true
GROUP BY created_date, commodity
