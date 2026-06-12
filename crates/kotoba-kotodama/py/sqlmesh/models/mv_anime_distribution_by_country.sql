-- Anime distribution: title and platform count per country.
MODEL (
  name dev.mv_anime_distribution_by_country,
  kind FULL,
  dialect postgres,
  description 'Distinct title and platform counts per country from vertex_anime_distribution.',
  grain [country],
  tags [anime, distribution, country]
);

SELECT
  country,
  COUNT(DISTINCT title_did) AS title_count,
  COUNT(DISTINCT platform_did) AS platform_count
FROM vertex_anime_distribution
GROUP BY country
