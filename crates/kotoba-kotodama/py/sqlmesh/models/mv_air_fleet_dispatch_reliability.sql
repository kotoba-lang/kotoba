-- Airline MRO fleet dispatch reliability and MTBF per aircraft type and carrier.
MODEL (
  name dev.mv_air_fleet_dispatch_reliability,
  kind FULL,
  dialect postgres,
  description 'Avg dispatch reliability and MTBF per aircraft_type/carrier from vertex_air_mro_reliability_report.',
  grain [aircraft_type, carrier_code],
  tags [air, mro, fleet, dispatch, reliability, mtbf]
);

SELECT
  aircraft_type,
  carrier_code,
  AVG(dispatch_reliability) AS avg_dispatch_reliability,
  AVG(mtbf_hours) AS avg_mtbf
FROM vertex_air_mro_reliability_report
GROUP BY aircraft_type, carrier_code
