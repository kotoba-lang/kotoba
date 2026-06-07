-- Active unexecuted arbitrage proposals with score and risk notes.
MODEL (
  name dev.mv_arb_active_opps,
  kind FULL,
  dialect postgres,
  description 'Active unexecuted arbitrage proposals joined with scoring from vertex_arb_proposal and vertex_arb_score.',
  grain [vertex_id],
  tags [arb, arbitrage, proposal, active, score]
);

SELECT
  p.vertex_id,
  p.proposal_id,
  p.asset_class,
  p.leg_a,
  p.leg_b,
  p.spread_bps,
  p.edge_bps,
  p.confidence,
  p.expires_at,
  s.score,
  s.risk_notes
FROM vertex_arb_proposal p
LEFT JOIN vertex_arb_score s ON s.proposal_id = p.proposal_id
WHERE p.executed = false
