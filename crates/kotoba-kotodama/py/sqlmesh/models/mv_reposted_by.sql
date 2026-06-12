-- Reposted by: flat projection of edge_reposts for inverse repost lookup.
MODEL (
  name dev.mv_reposted_by,
  kind FULL,
  dialect postgres,
  description 'Flat projection of edge_reposts for reposted-by lookups (dst_vid as anchor).',
  grain [edge_id],
  tags [social, repost, edge]
);

SELECT
  dst_vid,
  src_vid,
  edge_id,
  rkey,
  repo,
  subject_uri,
  _seq
FROM edge_reposts
