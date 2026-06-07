-- ADR-2605080500: SQLMesh Phase 0 source-of-truth for mv_shosha_approval_summary
-- Per-trade approval decision counts, latest decision time, and total notional.
MODEL (
  name dev.mv_shosha_approval_summary,
  kind FULL,
  dialect postgres,
  description 'Per-trade approval decision summary (active approvals only).',
  grain [ref_trade_id, decision],
  tags [shosha, approval, trading, materialized_view, adr_2605080500]
);

SELECT
  ref_trade_id,
  decision,
  COUNT(*)                               AS decision_count,
  MAX(decided_at)                        AS last_decided_at,
  SUM(COALESCE(amount_usd_at_decision, 0)) AS total_amount_usd
FROM vertex_shosha_approval
WHERE status = 'active'
GROUP BY ref_trade_id, decision
