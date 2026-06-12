-- Airline flight ops dispatch: total and active flight count per carrier and departure date.
MODEL (
  name dev.mv_air_flight_ops_status,
  kind FULL,
  dialect postgres,
  description 'Total and active flight counts per carrier_code and dep_date from vertex_air_ops_dispatch_brief.',
  grain [carrier_code, dep_date],
  tags [air, flight_ops, status, dispatch, carrier]
);

SELECT
  carrier_code,
  dep_date,
  COUNT(*) AS total_flights,
  COUNT(*) FILTER (WHERE status = 'active') AS active_flights
FROM vertex_air_ops_dispatch_brief
GROUP BY carrier_code, dep_date
