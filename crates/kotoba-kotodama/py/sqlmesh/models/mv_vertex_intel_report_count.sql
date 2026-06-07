-- Vertex intel report count: per-actor intel report count.
MODEL (
  name dev.mv_vertex_intel_report_count,
  kind FULL,
  dialect postgres,
  description 'Per actor_id: intel report count from vertex_intel_report.',
  grain [actor_id],
  tags [intel, report, count]
);

SELECT
  actor_id,
  COUNT(*)::BIGINT AS cnt
FROM vertex_intel_report
GROUP BY actor_id
