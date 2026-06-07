-- Feed timeline: streaming pre-computed viewer timeline (follows × posts).
MODEL (
  name dev.mv_feed_timeline,
  kind FULL,
  dialect postgres,
  description 'Per viewer: post_id, author, rkey, and seq from followed actors (edge_follows JOIN vertex_post).',
  grain [viewer, post_id],
  tags [social, feed, timeline, follows, posts]
);

SELECT
  f.src_vid AS viewer,
  p.vertex_id AS post_id,
  p.repo AS author,
  p.rkey,
  p._seq
FROM edge_follows f
JOIN vertex_post p ON p.repo = f.dst_vid
