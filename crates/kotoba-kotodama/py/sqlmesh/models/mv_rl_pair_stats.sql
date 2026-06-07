-- RL pair stats: per-action_nsid preference pair stats.
MODEL (
  name dev.mv_rl_pair_stats,
  kind FULL,
  dialect postgres,
  description 'Per action_nsid: pair count, mean/min/max reward delta, distinct chosen actors, last pair.',
  grain [action_nsid],
  tags [rl, pair, stats]
);

SELECT
  action_nsid,
  COUNT(*) AS total_pairs,
  AVG(reward_delta) AS mean_delta,
  MIN(reward_delta) AS min_delta,
  MAX(reward_delta) AS max_delta,
  COUNT(DISTINCT chosen_actor_did) AS distinct_chosen_actors,
  MAX(created_at) AS last_pair_at
FROM vertex_rl_preference_pair
GROUP BY action_nsid
