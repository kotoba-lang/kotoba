-- Animeka open retake count per repo and cut.
MODEL (
  name dev.mv_animeka_open_retake_by_cut,
  kind FULL,
  dialect postgres,
  description 'Count of open retakes per repo and cut_id from vertex_animeka retake collection.',
  grain [repo, cut_id],
  tags [animeka, retake, open, cut]
);

SELECT
  COALESCE(repo, '') AS repo,
  COALESCE(cut_id, '') AS cut_id,
  COUNT(*)::BIGINT AS open_cnt
FROM vertex_animeka
WHERE collection = 'com.etzhayyim.apps.animeka.retake'
  AND COALESCE(status, 'open') = 'open'
GROUP BY 1, 2
