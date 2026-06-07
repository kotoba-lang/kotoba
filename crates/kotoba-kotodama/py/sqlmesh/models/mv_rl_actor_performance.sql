-- RL actor performance: per-actor 24h reward stats.
MODEL (
  name dev.mv_rl_actor_performance,
  kind FULL,
  dialect postgres,
  description 'Per actor_did (last 24h): step count, mean reward, mean eta/spirit, floor violations, last step.',
  grain [actor_did],
  tags [rl, actor, performance]
);

SELECT
  actor_did,
  COUNT(*) AS total_steps,
  AVG(reward_scalar) AS mean_reward,
  AVG(reward_eta) FILTER (WHERE reward_eta IS NOT NULL) AS mean_eta,
  AVG(reward_spirit) FILTER (WHERE reward_spirit IS NOT NULL) AS mean_spirit,
  SUM(CASE WHEN reward_floor = FALSE THEN 1 ELSE 0 END) AS floor_violations,
  MAX(created_at) AS last_step_at
FROM vertex_rl_step
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY actor_did
