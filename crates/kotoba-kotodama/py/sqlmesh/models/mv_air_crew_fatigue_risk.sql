-- Airline crew fatigue risk: max cumulative duty hours and limit breach flag per crew.
MODEL (
  name dev.mv_air_crew_fatigue_risk,
  kind FULL,
  dialect postgres,
  description 'Per-crew max 28d/365d cumulative duty time and limit breach flag from vertex_air_crew_duty_time.',
  grain [crew_did],
  tags [air, crew, fatigue, risk, duty_time]
);

SELECT
  crew_did,
  MAX(cumulative_28d) AS max_28d,
  MAX(cumulative_365d) AS max_365d,
  BOOL_OR(limit_breach) AS any_breach
FROM vertex_air_crew_duty_time
GROUP BY crew_did
