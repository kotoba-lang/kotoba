-- Open retake queue per repo, cut, stage, and severity from edge_retakes.
MODEL (
  name dev.mv_animeka_retake_queue,
  kind FULL,
  dialect postgres,
  description 'Count of open retakes per repo, cut_id, stage, severity from edge_retakes.',
  grain [repo, cut_id, stage, severity],
  tags [animeka, retake, queue, stage, severity]
);

SELECT
  COALESCE(repo, '') AS repo,
  COALESCE(cut_id, '') AS cut_id,
  COALESCE(stage, '') AS stage,
  COALESCE(severity, 'minor') AS severity,
  COUNT(*)::BIGINT AS open_cnt
FROM edge_retakes
WHERE COALESCE(status, 'open') = 'open'
GROUP BY 1, 2, 3, 4
