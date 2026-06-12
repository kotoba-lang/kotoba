-- Handotai article category counts: article counts and latest publish date per category.
MODEL (
  name dev.mv_handotai_article_category_counts,
  kind FULL,
  dialect postgres,
  description 'Per category: article count and latest published_at from vertex_handotai_article.',
  grain [category],
  tags [handotai, article, category]
);

SELECT
  category,
  COUNT(*) AS article_count,
  MAX(published_at) AS latest_published_at
FROM vertex_handotai_article
GROUP BY category
