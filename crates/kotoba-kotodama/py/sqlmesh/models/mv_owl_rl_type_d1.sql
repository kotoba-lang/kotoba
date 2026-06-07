-- OWL RL type depth 1: rdf:type closure via SubClassOf/EquivalentClasses (1 hop).
MODEL (
  name dev.mv_owl_rl_type_d1,
  kind FULL,
  dialect postgres,
  description 'Per (subject, superclass): 1-hop rdf:type inference via SubClassOf/EquivalentClasses.',
  grain [subject, superclass],
  tags [owl, rl, type, d1, inference]
);

SELECT
  t.subject,
  'rdf:type' AS predicate,
  e.to_vertex_id AS superclass
FROM v_rdf_triple t
JOIN edge_owl_subclass e
  ON e.from_vertex_id = t.object
  AND t.predicate = 'rdf:type'
  AND e.axiom_type IN ('SubClassOf', 'EquivalentClasses')
