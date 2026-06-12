-- Etzhayyimcojp omega daily: daily omega score aggregates from governance events.
MODEL (
  name dev.mv_etzhayyimcojp_omega_daily,
  kind FULL,
  dialect postgres,
  description 'Per day: avg/min/max omega score and floor violation flag from vertex_etzhayyimcojp_governance_event.',
  grain [day],
  tags [etzhayyimcojp, omega, governance, daily]
);

SELECT
  DATE(created_at::TIMESTAMP) AS day,
  AVG(omega_score) AS avg_omega,
  MIN(omega_score) AS min_omega,
  MAX(omega_score) AS max_omega,
  COUNT(*) AS check_count,
  BOOL_OR(floor_violated) AS any_floor_violated
FROM vertex_etzhayyimcojp_governance_event
WHERE omega_score IS NOT NULL
GROUP BY DATE(created_at::TIMESTAMP)
