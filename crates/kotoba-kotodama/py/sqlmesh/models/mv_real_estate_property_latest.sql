-- Real estate property latest: deduplicated property representatives per canonical key.
MODEL (
  name dev.mv_real_estate_property_latest,
  kind FULL,
  dialect postgres,
  description 'Per canonical_property_key: representative vertex_id, country/type/city, latest observed, source row count.',
  grain [canonical_property_key],
  tags [real_estate, property, latest]
);

SELECT
  canonical_property_key,
  MAX(vertex_id) AS representative_property_vid,
  MAX(country_iso2) AS country_iso2,
  MAX(property_type) AS property_type,
  MAX(city) AS city,
  MAX(postal_code) AS postal_code,
  MAX(geohash) AS geohash,
  MAX(observed_at) AS latest_observed_at,
  COUNT(*) AS source_row_count
FROM vertex_real_estate_property
GROUP BY canonical_property_key
