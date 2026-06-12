-- OWL RL subproperty: predicate inheritance via SubObjectPropertyOf.
MODEL (
  name dev.mv_owl_rl_subproperty,
  kind FULL,
  dialect postgres,
  description 'Per (subject, predicate, object): inferred triples via SubObjectPropertyOf axiom.',
  grain [subject, predicate, object],
  tags [owl, rl, subproperty, inference]
);

SELECT
  t.subject,
  e.to_vertex_id AS predicate,
  t.object
FROM v_rdf_triple t
JOIN edge_owl_subclass e
  ON e.from_vertex_id = t.predicate
  AND e.axiom_type = 'SubObjectPropertyOf'
