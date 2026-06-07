-- Per-belief system: actor count, avg binding strength, and high-binding actor count.
MODEL (
  name dev.mv_belief_actor_coverage,
  kind FULL,
  dialect postgres,
  description 'Per-belief actor count, avg binding strength, and high-binding (>0.7) actor count from mv_actor_belief_karma.',
  grain [belief_vertex_id],
  tags [belief, actor, coverage, binding, karma]
);

SELECT
  belief_vertex_id,
  belief_name,
  tradition,
  COUNT(DISTINCT actor_vid)               AS actor_count,
  AVG(binding_strength)                   AS avg_binding_strength,
  COUNT(CASE WHEN binding_strength > 0.7 THEN 1 END) AS high_binding_actor_count
FROM mv_actor_belief_karma
GROUP BY belief_vertex_id, belief_name, tradition
