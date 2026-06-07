-- Animeka keyframe count per repo, cut, and kind from edge_cut_has_keyframe.
MODEL (
  name dev.mv_animeka_frame_count_by_cut,
  kind FULL,
  dialect postgres,
  description 'Count of keyframes per repo, cut_id, and frame kind from edge_cut_has_keyframe.',
  grain [repo, cut_id, kind],
  tags [animeka, frame, cut, keyframe]
);

SELECT
  COALESCE(repo, '') AS repo,
  COALESCE(cut_id, '') AS cut_id,
  COALESCE(kind, 'unknown') AS kind,
  COUNT(*)::BIGINT AS frame_cnt
FROM edge_cut_has_keyframe
GROUP BY 1, 2, 3
