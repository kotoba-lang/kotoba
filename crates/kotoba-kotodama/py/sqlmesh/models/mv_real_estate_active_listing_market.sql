-- Real estate active listing market: active/pending listings aggregated by market.
MODEL (
  name dev.mv_real_estate_active_listing_market,
  kind FULL,
  dialect postgres,
  description 'Per (country_iso2, city, listing_kind, currency): listing count, price stats, latest seen.',
  grain [country_iso2, city, listing_kind, currency],
  tags [real_estate, listing, market, active]
);

SELECT
  country_iso2,
  city,
  listing_kind,
  currency,
  COUNT(*) AS listing_count,
  AVG(price) AS avg_price,
  MIN(price) AS min_price,
  MAX(price) AS max_price,
  AVG(price_per_sqm) AS avg_price_per_sqm,
  MAX(last_seen_at) AS latest_seen_at
FROM vertex_real_estate_listing
WHERE offer_status IN ('active', 'pending')
GROUP BY country_iso2, city, listing_kind, currency
