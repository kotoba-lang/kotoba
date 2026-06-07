-- Flight offer source coverage: offers observed per source-airline pair.
MODEL (
  name dev.mv_flight_offer_source_coverage,
  kind FULL,
  dialect postgres,
  description 'Per (provider, airline): offer count, min total price, and last observed timestamp.',
  grain [source_id, iata_code],
  tags [flight, offer, source, coverage, airline]
);

SELECT
  provider AS source_id,
  airline AS iata_code,
  COUNT(*)::BIGINT AS offers_observed,
  MIN(total_price)::DOUBLE PRECISION AS min_total_price,
  MAX(observed_at) AS last_observed_at
FROM vertex_flight_offer
WHERE provider IS NOT NULL AND provider <> ''
  AND airline IS NOT NULL AND airline <> ''
GROUP BY provider, airline
