-- Kenkyusha hypothesis status counts: hypothesis counts and avg confidence per frontier and status.
MODEL (
  name dev.mv_kenkyusha_hypothesis_status_counts,
  kind FULL,
  dialect postgres,
  description 'Per (frontier_id, status): hypothesis count and avg confidence_score.',
  grain [frontier_id, status],
  tags [kenkyusha, hypothesis, status]
);

SELECT
  frontier_id,
  status,
  COUNT(*)::BIGINT AS hypothesis_count,
  AVG(confidence_score) AS avg_confidence_score
FROM vertex_kenkyusha_hypothesis
GROUP BY frontier_id, status
