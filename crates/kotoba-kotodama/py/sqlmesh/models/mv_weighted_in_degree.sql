-- Weighted in-degree: per-vertex follower count weighted by source out-degree.
MODEL (
  name dev.mv_weighted_in_degree,
  kind FULL,
  dialect postgres,
  description 'Per dst_vid: in-degree count and weighted_score (sum of 1/out_degree).',
  grain [dst_vid],
  tags [graph, weighted, in_degree, follow]
);

SELECT
  f.dst_vid,
  COUNT(*) AS in_degree,
  SUM(1.0 / GREATEST(d.out_degree, 1)) AS weighted_score
FROM edge_follows f
JOIN dev.mv_follow_out_degree d ON d.src_vid = f.src_vid
GROUP BY f.dst_vid
