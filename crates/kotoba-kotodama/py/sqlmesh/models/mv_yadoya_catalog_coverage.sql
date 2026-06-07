-- Yadoya catalog coverage: hotel counts per (country, region, ISIC, status).
MODEL (
  name dev.mv_yadoya_catalog_coverage,
  kind FULL,
  dialect postgres,
  description 'Per (country, region, isic_code, status): hotel count from vertex_yadoya_hotel.',
  grain [country, region, isic_code, status],
  tags [yadoya, catalog, hotel, coverage]
);

SELECT
  country,
  region,
  isic_code,
  status,
  COUNT(*) AS hotel_count
FROM vertex_yadoya_hotel
GROUP BY country, region, isic_code, status
