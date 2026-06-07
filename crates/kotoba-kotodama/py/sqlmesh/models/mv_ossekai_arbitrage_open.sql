-- Ossekai arbitrage open: open arbitrage opportunities aggregated by kind.
MODEL (
  name dev.mv_ossekai_arbitrage_open,
  kind FULL,
  dialect postgres,
  description 'Per opportunity_kind: count, avg confidence, total estimated value for open opportunities.',
  grain [opportunity_kind],
  tags [ossekai, arbitrage, open]
);

SELECT
  opportunity_kind,
  COUNT(*) AS opportunity_count,
  AVG(confidence_score) AS avg_confidence,
  SUM(estimated_value) AS total_estimated_value
FROM vertex_ossekai_arbitrage
WHERE status = 'open'
GROUP BY opportunity_kind
