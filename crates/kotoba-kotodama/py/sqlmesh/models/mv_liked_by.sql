-- Liked by: flat projection of edge_likes for inverse like lookup.
MODEL (
  name dev.mv_liked_by,
  kind FULL,
  dialect postgres,
  description 'Flat projection of edge_likes for liked-by lookups (dst_vid as anchor).',
  grain [edge_id],
  tags [social, like, edge]
);

SELECT
  dst_vid,
  src_vid,
  edge_id,
  rkey,
  repo,
  subject_uri,
  _seq
FROM edge_likes
