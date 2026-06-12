-- Etzhayyim path depth distribution: DID count per depth level.
MODEL (
  name dev.mv_etzhayyim_path_depth_dist,
  kind FULL,
  dialect postgres,
  description 'Per depth: count of DIDs at that depth in the path hierarchy.',
  grain [depth],
  tags [etzhayyim, did, path, depth]
);

SELECT
  depth,
  COUNT(*) AS dids
FROM vertex_etzhayyim_identity
WHERE depth IS NOT NULL
GROUP BY depth
