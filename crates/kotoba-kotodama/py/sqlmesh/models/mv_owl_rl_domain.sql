-- OWL RL domain: rdf:type inference via property domain axiom.
MODEL (
  name dev.mv_owl_rl_domain,
  kind FULL,
  dialect postgres,
  description 'Per (subject, predicate, inferred_class): rdf:type inference via property domain.',
  grain [subject, inferred_class],
  tags [owl, rl, domain, inference]
);

SELECT
  t.subject,
  'rdf:type' AS predicate,
  d.to_vertex_id AS inferred_class
FROM v_rdf_triple t
JOIN edge_owl_property_domain d ON d.from_vertex_id = t.predicate
