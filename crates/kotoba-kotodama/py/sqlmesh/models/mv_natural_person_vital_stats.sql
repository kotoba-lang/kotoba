-- Natural person vital stats: person count per era and vital status.
MODEL (
  name dev.mv_natural_person_vital_stats,
  kind FULL,
  dialect postgres,
  description 'Per (era, vital_status): person count from vertex_natural_person_cohort_person.',
  grain [era, vital_status],
  tags [natural_person, vital, era, cohort]
);

SELECT
  era,
  vital_status,
  COUNT(*) AS person_count
FROM vertex_natural_person_cohort_person
GROUP BY era, vital_status
