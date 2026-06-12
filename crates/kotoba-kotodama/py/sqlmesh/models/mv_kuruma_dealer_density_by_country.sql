-- Kuruma dealer density by country: dealer counts per app host parsed from kuruma DID.
MODEL (
  name dev.mv_kuruma_dealer_density_by_country,
  kind FULL,
  dialect postgres,
  description 'Per app_host: dealer count from vertex_repo_record where collection is car_dealer.dealer.',
  grain [app_host],
  tags [kuruma, dealer, density, country]
);

SELECT
  SPLIT_PART(SPLIT_PART(repo, '.etzhayyim.com', 1), 'did:web:', 2) AS app_host,
  CAST(NULL AS VARCHAR) AS country,
  COUNT(*)::BIGINT AS dealer_count
FROM vertex_repo_record
WHERE collection = 'com.etzhayyim.apps.car_dealer.dealer'
  AND repo = 'did:web:kuruma.etzhayyim.com'
GROUP BY SPLIT_PART(SPLIT_PART(repo, '.etzhayyim.com', 1), 'did:web:', 2)
