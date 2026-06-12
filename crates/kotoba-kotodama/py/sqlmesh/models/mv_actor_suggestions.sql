-- Active actors for suggestion / discovery.
MODEL (
  name dev.mv_actor_suggestions,
  kind FULL,
  dialect postgres,
  description 'Active actor subset for discovery suggestions from vertex_actor.',
  grain [vertex_id],
  tags [actor, discovery, suggestions]
);

SELECT vertex_id, did, handle, display_name, status
FROM vertex_actor
WHERE status = 'active'
