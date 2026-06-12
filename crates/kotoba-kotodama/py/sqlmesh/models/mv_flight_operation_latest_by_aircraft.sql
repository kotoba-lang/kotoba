-- Flight operation latest by aircraft: most recent operation status per aircraft.
MODEL (
  name dev.mv_flight_operation_latest_by_aircraft,
  kind FULL,
  dialect postgres,
  description 'Per aircraft_did: latest as_of, delay_minutes, occupancy_rate, status, and operator from vertex_flight_operation.',
  grain [aircraft_did],
  tags [flight, aircraft, operation, status, latest]
);

SELECT
  aircraft_did,
  MAX(as_of) AS as_of_latest,
  MAX(delay_minutes) AS delay_minutes_latest,
  MAX(occupancy_rate) AS occupancy_rate_latest,
  MAX(status) AS status_latest,
  MAX(operator_did) AS operator_did_latest
FROM vertex_flight_operation
WHERE aircraft_did IS NOT NULL AND aircraft_did <> ''
GROUP BY aircraft_did
