-- Repository ref heads: per-ref head commit linkage via edge_repository_ref_points.
MODEL (
  name dev.mv_repository_ref_heads,
  kind FULL,
  dialect postgres,
  description 'Per repository ref: owner, name, kind, head commit hash and pointed vertex_id.',
  grain [owner_did, ref_name],
  tags [repository, ref, head]
);

SELECT
  r.owner_did,
  r.ref_name,
  r.kind,
  r.head_commit_hash,
  r.updated_at,
  p.dst_vid AS head_commit_vid
FROM vertex_repository_ref r
LEFT JOIN edge_repository_ref_points p ON p.src_vid = r.vertex_id
