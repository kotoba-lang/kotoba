-- Audits for mv_shosha_exposure_by_commodity and mv_shosha_exposure_by_counterparty (ADR-2605080500)

AUDIT (
  name assert_exposure_commodity_open_count_nonneg,
  model dev.mv_shosha_exposure_by_commodity
)
SELECT *
FROM dev.mv_shosha_exposure_by_commodity
WHERE open_count < 0;

AUDIT (
  name assert_exposure_commodity_net_is_long_minus_short,
  model dev.mv_shosha_exposure_by_commodity
)
SELECT *
FROM dev.mv_shosha_exposure_by_commodity
WHERE ABS(net_usd - (gross_long_usd - gross_short_usd)) > 0.01;

AUDIT (
  name assert_exposure_counterparty_open_count_nonneg,
  model dev.mv_shosha_exposure_by_counterparty
)
SELECT *
FROM dev.mv_shosha_exposure_by_counterparty
WHERE open_count < 0;

AUDIT (
  name assert_exposure_counterparty_notional_nonneg,
  model dev.mv_shosha_exposure_by_counterparty
)
SELECT *
FROM dev.mv_shosha_exposure_by_counterparty
WHERE open_notional_usd < 0;
