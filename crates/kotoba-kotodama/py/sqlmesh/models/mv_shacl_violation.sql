-- SHACL violation: enabled SHACL shape constraints joined with rdf:type triples.
MODEL (
  name dev.mv_shacl_violation,
  kind FULL,
  dialect postgres,
  description 'Per (node_iri, shape_id): potential SHACL violations from enabled shapes targeting rdf:type instances.',
  grain [node_iri, shape_id],
  tags [shacl, violation, validation]
);

SELECT
  t.subject AS node_iri,
  s.vertex_id AS shape_id,
  s.severity,
  s.constraint_type,
  s.constraint_json
FROM v_rdf_triple t
JOIN vertex_shacl_shape s
  ON s.target_class = t.object
  AND t.predicate = 'rdf:type'
  AND s.enabled = TRUE
WHERE s.constraint_type IN ('minCount', 'maxCount', 'class', 'nodeKind')
