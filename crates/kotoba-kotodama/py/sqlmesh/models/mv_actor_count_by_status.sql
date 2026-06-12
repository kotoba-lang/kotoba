-- Actor count grouped by status.
MODEL (
  name dev.mv_actor_count_by_status,
  kind FULL,
  dialect postgres,
  description 'Actor row count per status value from vertex_actor.',
  grain [status],
  tags [actor, count, monitoring]
);

SELECT status, COUNT(*) AS cnt
FROM vertex_actor
GROUP BY status
