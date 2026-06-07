-- Compound element coverage: distinct compound count per element symbol.
MODEL (
  name dev.mv_compound_element_coverage,
  kind FULL,
  dialect postgres,
  description 'Per element symbol: distinct compound count and first edge timestamp from edge_compound_element.',
  grain [element_sym],
  tags [compound, element, coverage, chemistry]
);

SELECT
  ce.element_sym,
  COUNT(DISTINCT ce.compound_did)  AS compound_count,
  MIN(ce.created_at)               AS first_edge_at
FROM edge_compound_element ce
GROUP BY ce.element_sym
