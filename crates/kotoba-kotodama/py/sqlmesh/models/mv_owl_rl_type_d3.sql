-- OWL RL type depth 3: rdf:type closure via 3-hop SubClassOf/EquivalentClasses.
MODEL (
  name dev.mv_owl_rl_type_d3,
  kind FULL,
  dialect postgres,
  description 'Per (subject, superclass): 3-hop rdf:type inference via mv_owl_rl_type_d2.',
  grain [subject, superclass],
  tags [owl, rl, type, d3, inference]
);

SELECT
  d2.subject,
  'rdf:type' AS predicate,
  e.to_vertex_id AS superclass
FROM dev.mv_owl_rl_type_d2 d2
JOIN edge_owl_subclass e
  ON e.from_vertex_id = d2.superclass
  AND e.axiom_type IN ('SubClassOf', 'EquivalentClasses')
