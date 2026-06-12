-- ADR-2605080500: SQLMesh Phase 0 source-of-truth for mv_shosha_exposure_by_counterparty
-- Open-trade concentration per counterparty for comply_ok=true trades.
MODEL (
  name dev.mv_shosha_exposure_by_counterparty,
  kind FULL,
  dialect postgres,
  description 'Open-trade notional concentration per counterparty (comply_ok=true).',
  grain [counterparty_name],
  tags [shosha, exposure, counterparty, trading, materialized_view, adr_2605080500]
);

SELECT
  counterparty_name,
  COUNT(*) FILTER (WHERE status = 'open')                                      AS open_count,
  SUM(CASE WHEN status = 'open' THEN amount_usd ELSE 0 END)                   AS open_notional_usd,
  SUM(CASE WHEN side = 'buy'  AND status = 'open' THEN amount_usd ELSE 0 END) AS long_usd,
  SUM(CASE WHEN side = 'sell' AND status = 'open' THEN amount_usd ELSE 0 END) AS short_usd
FROM vertex_shosha_trade
WHERE comply_ok = true
GROUP BY counterparty_name
