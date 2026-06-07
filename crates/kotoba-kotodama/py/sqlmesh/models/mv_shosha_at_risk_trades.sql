-- ADR-2605080500: SQLMesh Phase 0 source-of-truth for mv_shosha_at_risk_trades
-- Risk monitor: open/pending trades flagged by 4 risk classes.
-- risk_class values: comply-blocked | counterparty-sanctioned | large-pending | mtm-loss | unhedged
MODEL (
  name dev.mv_shosha_at_risk_trades,
  kind FULL,
  dialect postgres,
  description 'Shosha open/pending trades flagged by compliance, sanction, size, or MtM loss.',
  grain [vertex_id],
  tags [shosha, risk, trading, compliance, materialized_view, adr_2605080500]
);

SELECT
  t.vertex_id,
  t.trade_id,
  t.commodity,
  t.side,
  t.amount_usd,
  t.counterparty_name,
  t.approval_state,
  t.status,
  CASE
    WHEN t.comply_ok = false
      THEN 'comply-blocked'
    WHEN c.sanction_status IN ('flagged', 'blocked')
      THEN 'counterparty-sanctioned'
    WHEN t.approval_state = 'pending' AND t.amount_usd > 1000000
      THEN 'large-pending'
    WHEN t.status = 'open' AND COALESCE(t.pnl_unrealized, 0) < -100000
      THEN 'mtm-loss'
    ELSE 'unhedged'
  END AS risk_class,
  t.created_at
FROM vertex_shosha_trade t
LEFT JOIN vertex_shosha_counterparty c
  ON c.name = t.counterparty_name AND c.status = 'active'
WHERE t.status IN ('open', 'pending')
  AND (
    t.comply_ok = false
    OR c.sanction_status IN ('flagged', 'blocked')
    OR (t.approval_state = 'pending' AND t.amount_usd > 1000000)
    OR (t.status = 'open' AND COALESCE(t.pnl_unrealized, 0) < -100000)
  )
