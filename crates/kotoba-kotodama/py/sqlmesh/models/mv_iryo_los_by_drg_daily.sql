-- Iryo length of stay by DRG daily: per-(date, DRG) discharge LOS aggregates.
MODEL (
  name dev.mv_iryo_los_by_drg_daily,
  kind FULL,
  dialect postgres,
  description 'Per (created_date, drg_code): closed-encounter discharge count, avg/min/max LOS days.',
  grain [created_date, drg_code],
  tags [iryo, los, drg, daily]
);

SELECT
  created_date,
  drg_code,
  COUNT(*) AS discharge_count,
  AVG(length_of_stay_days::DOUBLE PRECISION) AS avg_los_days,
  MIN(length_of_stay_days) AS min_los_days,
  MAX(length_of_stay_days) AS max_los_days
FROM vertex_iryo_encounter
WHERE status = 'closed'
  AND drg_code IS NOT NULL
  AND length_of_stay_days IS NOT NULL
GROUP BY created_date, drg_code
