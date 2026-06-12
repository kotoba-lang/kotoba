-- Kiyo author h-index: per-author paper and citation aggregates from authored-by edges.
MODEL (
  name dev.mv_kiyo_author_hindex,
  kind FULL,
  dialect postgres,
  description 'Per author_did: total papers and total citations across paper stats MV.',
  grain [author_did],
  tags [kiyo, author, hindex, citations]
);

SELECT
  a.dst_vid AS author_did,
  COUNT(DISTINCT a.src_vid) AS total_papers,
  COALESCE(SUM(s.citation_in_count), 0) AS total_citations
FROM edge_kiyo_authored_by a
LEFT JOIN dev.mv_kiyo_paper_stats s ON s.vertex_id = a.src_vid
GROUP BY a.dst_vid
