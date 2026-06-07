-- Element material coverage: material count per periodic table element.
MODEL (
  name dev.mv_element_material_coverage,
  kind FULL,
  dialect postgres,
  description 'Per element (symbol, atomic_number, category): count of materials linked via edge_material_element.',
  grain [symbol],
  tags [periodic, element, material, coverage]
);

SELECT
  el.symbol,
  el.atomic_number,
  el.category,
  COUNT(eme.src_vid) AS material_count
FROM vertex_periodic_element el
LEFT JOIN edge_material_element eme ON eme.dst_vid = el.vertex_id
GROUP BY el.symbol, el.atomic_number, el.category
