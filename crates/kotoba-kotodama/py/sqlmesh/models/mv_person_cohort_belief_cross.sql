-- Person cohort belief cross: per-era cohort joined with dominant belief systems (region 001).
MODEL (
  name dev.mv_person_cohort_belief_cross,
  kind FULL,
  dialect postgres,
  description 'Per cohort era × belief system (region 001): adherent fraction, dominance rank.',
  grain [era_label, era_start_year, belief_vid],
  tags [person_cohort, belief, cross_domain]
);

SELECT
  c.era_label,
  c.era_start_year,
  c.estimated_population,
  b.adherent_fraction,
  b.dominance_rank,
  b.dst_vid AS belief_vid
FROM vertex_person_population_cohort c
JOIN edge_cohort_belief_system b ON b.src_vid = c.vertex_id
WHERE c.region_m49 = '001'
ORDER BY c.era_start_year ASC, b.dominance_rank ASC
