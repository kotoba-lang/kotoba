-- Vessel flag counts: vessel count per flag state.
MODEL (
  name dev.mv_vessel_flag_counts,
  kind FULL,
  dialect postgres,
  description 'Per flag_state: vessel count from vertex_logistics_vessel.',
  grain [flag_state],
  tags [vessel, maritime, flag]
);

SELECT
  flag_state,
  COUNT(*) AS vessel_count
FROM vertex_logistics_vessel
GROUP BY flag_state
