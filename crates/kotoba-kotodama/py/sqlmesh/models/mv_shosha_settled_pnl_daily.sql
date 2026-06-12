-- ADR-2605080500: SQLMesh Phase 0 source-of-truth for mv_shosha_settled_pnl_daily
-- Daily realized P&L for settled trades, joined with trade commodity/currency.
MODEL (
  name dev.mv_shosha_settled_pnl_daily,
  kind FULL,
  dialect postgres,
  description 'Daily settled-trade notional and realized P&L per commodity/currency.',
  grain [created_date, commodity, currency],
  tags [shosha, pnl, settlement, trading, materialized_view, adr_2605080500]
);

SELECT
  s.created_date,
  t.commodity,
  t.currency,
  COUNT(*)                               AS settled_count,
  SUM(COALESCE(s.amount_usd, 0))         AS settled_notional_usd,
  SUM(COALESCE(s.pnl_realized, 0))       AS realized_usd
FROM vertex_shosha_settlement s
JOIN vertex_shosha_trade t
  ON t.trade_id = s.ref_trade_id
WHERE s.status = 'settled'
GROUP BY s.created_date, t.commodity, t.currency
