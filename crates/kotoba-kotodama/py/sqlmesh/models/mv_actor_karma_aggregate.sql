-- Per-actor aggregate belief karma statistics.
MODEL (
  name dev.mv_actor_karma_aggregate,
  kind FULL,
  dialect postgres,
  description 'Per-actor aggregate over mv_actor_belief_karma: belief_count, individuation, binding strength.',
  grain [actor_vid],
  tags [actor, belief, karma, spirit, aggregate]
);

SELECT
  actor_vid,
  COUNT(*)                                              AS belief_count,
  AVG(self_other_separation)                            AS avg_individuation,
  SUM(binding_strength)                                 AS total_binding,
  CASE WHEN SUM(binding_strength) > 0
    THEN SUM(self_other_separation * binding_strength) / SUM(binding_strength)
    ELSE AVG(self_other_separation)
  END                                                   AS weighted_individuation
FROM mv_actor_belief_karma
GROUP BY actor_vid
