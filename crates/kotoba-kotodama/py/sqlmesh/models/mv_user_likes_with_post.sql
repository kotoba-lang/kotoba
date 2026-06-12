-- User likes with post: edge_likes joined with vertex_post for post metadata.
MODEL (
  name dev.mv_user_likes_with_post,
  kind FULL,
  dialect postgres,
  description 'Per (liker, post_vid): edge_likes + vertex_post (author repo, rkey).',
  grain [liker, post_vid],
  tags [social, like, post]
);

SELECT
  l.src_vid AS liker,
  l.dst_vid AS post_vid,
  p.repo AS author,
  p.rkey
FROM edge_likes l
JOIN vertex_post p ON p.vertex_id = l.dst_vid
