-- Yoro actor score counts: per-actor dojo and joucho score event counts.
MODEL (
  name dev.mv_yoro_actor_score_counts,
  kind FULL,
  dialect postgres,
  description 'Per actor_did: drills (dojo step completed) and reviews (joucho review) counts.',
  grain [actor_did],
  tags [yoro, actor, score, counts]
);

SELECT
  actor_did,
  COUNT(*) FILTER (WHERE kind = 'dojo') AS drills,
  COUNT(*) FILTER (WHERE kind = 'joucho') AS reviews
FROM (
  SELECT actor_did, 'dojo' AS kind FROM vertex_dojo_step_completed_event
  UNION ALL SELECT actor_did, 'joucho' AS kind FROM vertex_joucho_review
) events
GROUP BY actor_did
