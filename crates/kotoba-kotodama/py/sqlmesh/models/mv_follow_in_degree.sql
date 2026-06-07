-- Follow in-degree: number of followers per actor.
MODEL (
  name dev.mv_follow_in_degree,
  kind FULL,
  dialect postgres,
  description 'CSC of edge_follows: per dst_vid (followed actor) in-degree count.',
  grain [dst_vid],
  tags [social, follows, in_degree, graph]
);

SELECT dst_vid, COUNT(*) AS in_degree
FROM edge_follows
GROUP BY dst_vid
