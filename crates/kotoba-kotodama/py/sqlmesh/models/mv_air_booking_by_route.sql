-- Confirmed/ticketed airline bookings and total revenue per route and carrier.
MODEL (
  name dev.mv_air_booking_by_route,
  kind FULL,
  dialect postgres,
  description 'Booking count and total fare revenue per origin/dest/carrier from vertex_air_book_pnr.',
  grain [origin, dest, carrier_code],
  tags [air, booking, route, revenue, pnr]
);

SELECT
  origin,
  dest,
  carrier_code,
  COUNT(*) AS booking_count,
  SUM(total_fare) AS total_revenue
FROM vertex_air_book_pnr
WHERE status = 'confirmed' OR status = 'ticketed'
GROUP BY origin, dest, carrier_code
