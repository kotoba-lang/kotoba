-- OWL RL range: rdf:type inference for objects via property range axiom.
MODEL (
  name dev.mv_owl_rl_range,
  kind FULL,
  dialect postgres,
  description 'Per (object subject, inferred_class): rdf:type inference via property range axiom.',
  grain [subject, inferred_class],
  tags [owl, rl, range, inference]
);

SELECT
  t.object AS subject,
  'rdf:type' AS predicate,
  r.to_vertex_id AS inferred_class
FROM v_rdf_triple t
JOIN edge_owl_property_range r ON r.from_vertex_id = t.predicate
