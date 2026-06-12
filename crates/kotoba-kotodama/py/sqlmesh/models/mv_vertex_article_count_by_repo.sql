-- Vertex article count by repo: per-repo article count.
MODEL (
  name dev.mv_vertex_article_count_by_repo,
  kind FULL,
  dialect postgres,
  description 'Per repo: article count from vertex_article.',
  grain [repo],
  tags [article, count, repo]
);

SELECT
  COALESCE(repo, '') AS repo,
  COUNT(*)::BIGINT AS cnt
FROM vertex_article
GROUP BY 1
