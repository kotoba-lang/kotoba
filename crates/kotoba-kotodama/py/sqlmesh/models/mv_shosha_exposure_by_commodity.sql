-- ADR-2605080500: SQLMesh Phase 0 source-of-truth for mv_shosha_exposure_by_commodity
-- Net long/short exposure per commodity for comply_ok=true open trades.
MODEL (
  name dev.mv_shosha_exposure_by_commodity,
  kind FULL,
  dialect postgres,
  description 'Net long/short open-trade exposure per commodity (comply_ok=true).',
  grain [commodity, currency],
  tags [shosha, exposure, trading, materialized_view, adr_2605080500]
);

SELECT
  commodity,
  currency,
  COUNT(*) FILTER (WHERE status = 'open')                                                         AS open_count,
  SUM(CASE WHEN side = 'buy'  AND status = 'open' THEN amount_usd ELSE 0 END)                    AS gross_long_usd,
  SUM(CASE WHEN side = 'sell' AND status = 'open' THEN amount_usd ELSE 0 END)                    AS gross_short_usd,
  SUM(CASE WHEN side = 'buy'  AND status = 'open' THEN  amount_usd
           WHEN side = 'sell' AND status = 'open' THEN -amount_usd
           ELSE 0 END)                                                                            AS net_usd
FROM vertex_shosha_trade
WHERE comply_ok = true
GROUP BY commodity, currency
