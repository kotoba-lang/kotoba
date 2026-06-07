-- OWL RL type depth 2: rdf:type closure via 2-hop SubClassOf/EquivalentClasses.
MODEL (
  name dev.mv_owl_rl_type_d2,
  kind FULL,
  dialect postgres,
  description 'Per (subject, superclass): 2-hop rdf:type inference via mv_owl_rl_type_d1.',
  grain [subject, superclass],
  tags [owl, rl, type, d2, inference]
);

SELECT
  d1.subject,
  'rdf:type' AS predicate,
  e.to_vertex_id AS superclass
FROM dev.mv_owl_rl_type_d1 d1
JOIN edge_owl_subclass e
  ON e.from_vertex_id = d1.superclass
  AND e.axiom_type IN ('SubClassOf', 'EquivalentClasses')
