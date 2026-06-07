-- Phys material composition summary: per-material component counts and known fraction sum.
MODEL (
  name dev.mv_phys_material_composition_summary,
  kind FULL,
  dialect postgres,
  description 'Per (material_vid, component_kind): component count and known fraction sum from edge_phys_material_composed_of.',
  grain [material_vid, component_kind],
  tags [phys, material, composition]
);

SELECT
  src_vid AS material_vid,
  component_kind,
  COUNT(*)::BIGINT AS component_count,
  SUM(COALESCE(fraction_value, 0.0)) AS known_fraction_sum
FROM edge_phys_material_composed_of
GROUP BY src_vid, component_kind
