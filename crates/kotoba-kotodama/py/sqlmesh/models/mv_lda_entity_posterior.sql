-- LDA entity posterior: evidence count and weight aggregates per entity.
MODEL (
  name dev.mv_lda_entity_posterior,
  kind FULL,
  dialect postgres,
  description 'Per entity_vid: distinct evidence count, max evidence weight, and total evidence mass.',
  grain [entity_vid],
  tags [lda, entity, posterior, evidence]
);

SELECT
  e.dst_vid AS entity_vid,
  COUNT(DISTINCT e.src_vid) AS evidence_count,
  MAX(e.evidence_weight) AS max_evidence_weight,
  SUM(e.evidence_weight) AS total_evidence_mass
FROM edge_entity_evidence e
GROUP BY e.dst_vid
