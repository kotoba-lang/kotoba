-- Vertex sanctions entry count: per-(actor, list) sanctions entry count.
MODEL (
  name dev.mv_vertex_sanctions_entry_count,
  kind FULL,
  dialect postgres,
  description 'Per (actor_id, list_name): sanctions entry count from vertex_sanctions_entry.',
  grain [actor_id, list_name],
  tags [sanctions, entry, count]
);

SELECT
  actor_id,
  list_name,
  COUNT(*)::BIGINT AS cnt
FROM vertex_sanctions_entry
GROUP BY actor_id, list_name
