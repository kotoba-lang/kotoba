-- Mineral element composition: element count per mineral.
MODEL (
  name dev.mv_mineral_element_composition,
  kind FULL,
  dialect postgres,
  description 'Per mineral_did: element count and first_edge_at from edge_mineral_element.',
  grain [mineral_did],
  tags [mineral, element, composition]
);

SELECT
  em.mineral_did,
  COUNT(*) AS element_count,
  MIN(em.created_at) AS first_edge_at
FROM edge_mineral_element em
GROUP BY em.mineral_did
