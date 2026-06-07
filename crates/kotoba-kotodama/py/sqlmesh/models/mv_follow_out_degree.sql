-- Follow out-degree: number of accounts each actor follows.
MODEL (
  name dev.mv_follow_out_degree,
  kind FULL,
  dialect postgres,
  description 'CSR of edge_follows: per src_vid (follower) out-degree count.',
  grain [src_vid],
  tags [social, follows, out_degree, graph]
);

SELECT src_vid, COUNT(*) AS out_degree
FROM edge_follows
GROUP BY src_vid
