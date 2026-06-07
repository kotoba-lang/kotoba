-- Person cohort era summary: per-era population aggregates (region 001).
MODEL (
  name dev.mv_person_cohort_era_summary,
  kind FULL,
  dialect postgres,
  description 'Per era_label (region 001): start/end years, cohort count, population low/high/total, avg life expectancy.',
  grain [era_label],
  tags [person_cohort, era, summary]
);

SELECT
  era_label,
  MIN(era_start_year) AS era_start_year,
  MAX(era_end_year) AS era_end_year,
  COUNT(*) AS cohort_count,
  SUM(estimated_population) AS total_population,
  SUM(population_low) AS total_population_low,
  SUM(population_high) AS total_population_high,
  AVG(life_expectancy) AS avg_life_expectancy
FROM vertex_person_population_cohort
WHERE region_m49 = '001'
GROUP BY era_label
