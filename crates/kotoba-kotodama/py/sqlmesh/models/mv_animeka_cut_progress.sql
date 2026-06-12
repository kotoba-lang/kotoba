-- Animeka cut progress: retake count per repo and episode.
MODEL (
  name dev.mv_animeka_cut_progress,
  kind FULL,
  dialect postgres,
  description 'Per-repo/episode cut count and retake count from vertex_animeka cut collection.',
  grain [repo, episode_id],
  tags [animeka, cut, progress, retake]
);

SELECT
  COALESCE(repo, '') AS repo,
  COALESCE(episode_id, '') AS episode_id,
  COUNT(*)::BIGINT AS cut_count,
  SUM(CASE WHEN priority = 'retake' THEN 1 ELSE 0 END)::BIGINT AS retake_count
FROM vertex_animeka
WHERE collection = 'com.etzhayyim.apps.animeka.cut'
GROUP BY 1, 2
