-- Bunken era-country counts: item count per (era, country) pair.
MODEL (
  name dev.mv_bunken_era_country_counts,
  kind FULL,
  dialect postgres,
  description 'Per (era, country): bibliographic item count from vertex_bunken_bibliographic_item.',
  grain [era, country],
  tags [bunken, bibliographic, era, country, counts]
);

SELECT
  era,
  country,
  COUNT(*) AS item_count
FROM vertex_bunken_bibliographic_item
GROUP BY era, country
