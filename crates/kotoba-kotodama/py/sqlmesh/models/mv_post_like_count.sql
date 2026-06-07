-- Post like count: per-post like count from edge_likes.
MODEL (
  name dev.mv_post_like_count,
  kind FULL,
  dialect postgres,
  description 'Per dst_vid (post): like count from edge_likes.',
  grain [dst_vid],
  tags [post, like, count]
);

SELECT
  dst_vid,
  COUNT(*) AS like_count
FROM edge_likes
GROUP BY dst_vid
