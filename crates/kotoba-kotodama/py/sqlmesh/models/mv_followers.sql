-- Followers: reverse-indexed follow edges (CSC) for follower lookup.
MODEL (
  name dev.mv_followers,
  kind FULL,
  dialect postgres,
  description 'CSC of edge_follows: dst_vid (followed actor) as primary, src_vid (follower) as secondary.',
  grain [edge_id],
  tags [social, follows, followers, index]
);

SELECT dst_vid, src_vid, edge_id, rkey, repo, created_at, _seq
FROM edge_follows
