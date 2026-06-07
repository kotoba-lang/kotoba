-- Kenkyusha frontier status counts: frontier counts per discipline, urgency, and status.
MODEL (
  name dev.mv_kenkyusha_frontier_status_counts,
  kind FULL,
  dialect postgres,
  description 'Per (primary_discipline, urgency, status): frontier count from vertex_kenkyusha_frontier.',
  grain [primary_discipline, urgency, status],
  tags [kenkyusha, frontier, status]
);

SELECT
  primary_discipline,
  urgency,
  status,
  COUNT(*)::BIGINT AS frontier_count
FROM vertex_kenkyusha_frontier
GROUP BY primary_discipline, urgency, status
