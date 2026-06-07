-- Phys ontology counts: vertex counts across element/isotope/molecule/material tables.
MODEL (
  name dev.mv_phys_ontology_counts,
  kind FULL,
  dialect postgres,
  description 'Per kind (element/isotope/molecule/material): vertex count from phys ontology spine.',
  grain [kind],
  tags [phys, ontology, counts]
);

SELECT 'element' AS kind, COUNT(*)::BIGINT AS vertex_count FROM vertex_phys_element
UNION ALL SELECT 'isotope', COUNT(*)::BIGINT FROM vertex_phys_isotope
UNION ALL SELECT 'molecule', COUNT(*)::BIGINT FROM vertex_phys_molecule
UNION ALL SELECT 'material', COUNT(*)::BIGINT FROM vertex_phys_material
