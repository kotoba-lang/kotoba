-- Follow with actor: enriched follow edges with actor handle and display_name.
MODEL (
  name dev.mv_follow_with_actor,
  kind FULL,
  dialect postgres,
  description 'Follow edges joined with vertex_actor for followed actor handle and display_name.',
  grain [src_vid, dst_vid],
  tags [social, follows, actor, enriched]
);

SELECT f.src_vid, f.dst_vid, a.did, a.handle, a.display_name
FROM edge_follows f
JOIN vertex_actor a ON a.vertex_id = f.dst_vid
