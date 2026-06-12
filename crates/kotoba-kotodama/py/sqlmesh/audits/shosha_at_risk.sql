-- Audits for mv_shosha_at_risk_trades (ADR-2605080500)

AUDIT (
  name assert_no_null_risk_class,
  model dev.mv_shosha_at_risk_trades
)
SELECT *
FROM dev.mv_shosha_at_risk_trades
WHERE risk_class IS NULL;

AUDIT (
  name assert_at_risk_status_is_open_or_pending,
  model dev.mv_shosha_at_risk_trades
)
SELECT *
FROM dev.mv_shosha_at_risk_trades
WHERE status NOT IN ('open', 'pending');
