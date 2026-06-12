-- Replied by: flat projection of edge_reply for inverse reply lookup.
MODEL (
  name dev.mv_replied_by,
  kind FULL,
  dialect postgres,
  description 'Flat projection of edge_reply for replied-by lookups (dst_vid as anchor).',
  grain [edge_id],
  tags [social, reply, edge]
);

SELECT
  dst_vid,
  src_vid,
  edge_id,
  _seq
FROM edge_reply
