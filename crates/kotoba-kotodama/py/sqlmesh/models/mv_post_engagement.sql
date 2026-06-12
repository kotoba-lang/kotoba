-- Post engagement: per-post like + repost engagement aggregates.
MODEL (
  name dev.mv_post_engagement,
  kind FULL,
  dialect postgres,
  description 'Per post: author, rkey, like_count, repost_count, total_engagement.',
  grain [post_id],
  tags [post, engagement, social]
);

SELECT
  p.vertex_id AS post_id,
  p.repo AS author,
  p.rkey,
  COALESCE(l.like_count, 0) AS like_count,
  COALESCE(r.repost_count, 0) AS repost_count,
  COALESCE(l.like_count, 0) + COALESCE(r.repost_count, 0) AS total_engagement
FROM vertex_post p
LEFT JOIN dev.mv_post_like_count l ON l.dst_vid = p.vertex_id
LEFT JOIN (
  SELECT dst_vid, COUNT(*) AS repost_count
  FROM edge_reposts
  GROUP BY dst_vid
) r ON r.dst_vid = p.vertex_id
