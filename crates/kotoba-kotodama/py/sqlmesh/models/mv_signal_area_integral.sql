-- Signal area integral: per-tick a_info, eta_global, and coverage grade.
MODEL (
  name dev.mv_signal_area_integral,
  kind FULL,
  dialect postgres,
  description 'Per tick: a_info (sum of area_contrib), eta_global = a_info/4.475, and coverage grade.',
  grain [tick],
  tags [signal, area, integral, aria]
);

SELECT
  tick,
  SUM(area_contrib) AS a_info,
  SUM(area_contrib) / 4.475 AS eta_global,
  CASE
    WHEN SUM(area_contrib) < 1.567 THEN 'BELOW_BASELINE'
    WHEN SUM(area_contrib) < 3.0 THEN 'PARTIAL'
    ELSE 'OPTIMAL'
  END AS coverage_grade
FROM dev.mv_signal_entropy
GROUP BY tick
