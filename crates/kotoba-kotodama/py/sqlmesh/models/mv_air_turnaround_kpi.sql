-- Airline DCS boarded passenger count per flight and departure date (turnaround KPI).
MODEL (
  name dev.mv_air_turnaround_kpi,
  kind FULL,
  dialect postgres,
  description 'Count of boarded passengers per flight_no and dep_date from vertex_air_dcs_checkin.',
  grain [flight_no, dep_date],
  tags [air, turnaround, kpi, dcs, checkin]
);

SELECT
  flight_no,
  dep_date,
  COUNT(DISTINCT vertex_id) AS pax_checkin_count
FROM vertex_air_dcs_checkin
WHERE status = 'boarded'
GROUP BY flight_no, dep_date
