-- Per-actor belief constraint profile: individuation score and total constraint load.
MODEL (
  name dev.mv_belief_constraint_profile,
  kind FULL,
  dialect postgres,
  description 'Per-actor avg individuation, belief constraint count, and total constraint load via edge_constrained_by.',
  grain [actor_vid],
  tags [belief, actor, constraint, individuation, karma]
);

SELECT
  ec.src_vid                                AS actor_vid,
  AVG(bs.self_other_separation)             AS individuation_score,
  COUNT(DISTINCT ec.dst_vid)                AS belief_constraint_count,
  SUM(COALESCE(ec.binding_strength, 0.5))   AS total_constraint_load
FROM edge_constrained_by ec
JOIN vertex_belief_system bs ON bs.vertex_id = ec.dst_vid
GROUP BY ec.src_vid
