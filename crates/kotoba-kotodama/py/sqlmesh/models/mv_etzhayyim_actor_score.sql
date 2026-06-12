-- Etzhayyim actor score: verified method count and trust score per DID.
MODEL (
  name dev.mv_etzhayyim_actor_score,
  kind FULL,
  dialect postgres,
  description 'Per DID: verified method count, total method count, and actor score (capped at 100).',
  grain [did],
  tags [etzhayyim, actor, score, trust]
);

SELECT
  src_vid AS did,
  COUNT(*) FILTER (WHERE verified = 1) AS verified_method_count,
  COUNT(*) AS total_method_count,
  LEAST(COUNT(*) FILTER (WHERE verified = 1) * 25, 100) AS actor_score
FROM edge_etzhayyim_authenticates
GROUP BY src_vid
