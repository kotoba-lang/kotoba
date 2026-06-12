-- Flight offer cheapest by route date: lowest price offer per route and departure date.
MODEL (
  name dev.mv_flight_offer_cheapest_by_route_date,
  kind FULL,
  dialect postgres,
  description 'Per (origin, destination, outbound_date, currency): cheapest price with booking URL, provider, and observed timestamp.',
  grain [origin_iata, destination_iata, outbound_date, currency],
  tags [flight, offer, cheapest, route, price]
);

WITH best AS (
  SELECT
    origin_iata,
    destination_iata,
    outbound_date,
    currency,
    MIN(total_price)::DOUBLE PRECISION AS cheapest_total_price
  FROM vertex_flight_offer
  WHERE origin_iata IS NOT NULL AND origin_iata <> ''
    AND destination_iata IS NOT NULL AND destination_iata <> ''
    AND outbound_date IS NOT NULL AND outbound_date <> ''
    AND currency IS NOT NULL AND currency <> ''
    AND total_price IS NOT NULL
  GROUP BY origin_iata, destination_iata, outbound_date, currency
)
SELECT
  b.origin_iata,
  b.destination_iata,
  b.outbound_date,
  b.currency,
  b.cheapest_total_price,
  MAX(v.booking_url) AS cheapest_booking_url,
  MAX(v.provider) AS cheapest_provider,
  MAX(v.observed_at) AS cheapest_observed_at
FROM best b
LEFT JOIN vertex_flight_offer v
  ON v.origin_iata = b.origin_iata
 AND v.destination_iata = b.destination_iata
 AND v.outbound_date = b.outbound_date
 AND v.currency = b.currency
 AND v.total_price = b.cheapest_total_price
GROUP BY b.origin_iata, b.destination_iata, b.outbound_date, b.currency, b.cheapest_total_price
