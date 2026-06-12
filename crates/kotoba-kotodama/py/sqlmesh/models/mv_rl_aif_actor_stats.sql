-- RL AIF actor stats: per-actor active inference belief stats.
MODEL (
  name dev.mv_rl_aif_actor_stats,
  kind FULL,
  dialect postgres,
  description 'Per actor_did: belief count, mean/min/max free energy, last belief timestamp.',
  grain [actor_did],
  tags [rl, aif, belief, actor]
);

SELECT
  b.actor_did,
  COUNT(*) AS total_beliefs,
  AVG(b.free_energy) AS mean_free_energy,
  MIN(b.free_energy) AS min_free_energy,
  MAX(b.free_energy) AS max_free_energy,
  MAX(b.updated_at) AS last_belief_at
FROM vertex_rl_aif_belief b
GROUP BY b.actor_did
