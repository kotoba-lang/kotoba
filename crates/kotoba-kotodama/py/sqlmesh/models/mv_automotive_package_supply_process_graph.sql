-- Automotive package supply process graph: counts of supply chain elements per product package.
MODEL (
  name dev.mv_automotive_package_supply_process_graph,
  kind FULL,
  dialect postgres,
  description 'Per automotive product package: material, intermediate, process, responsibility, supplier entity, and patent counts.',
  grain [package_id],
  tags [automotive, supply_chain, manufacturing, package, process]
);

SELECT
  p.package_id,
  p.product_id,
  p.revision,
  p.asset_kind,
  COUNT(DISTINCT m.vertex_id) AS material_count,
  COUNT(DISTINCT ip.vertex_id) AS intermediate_count,
  COUNT(DISTINCT pr.vertex_id) AS process_count,
  COUNT(DISTINCT rp.vertex_id) AS responsibility_count,
  COUNT(DISTINCT ms.dst_vid) AS supplier_entity_count,
  COUNT(DISTINCT pp.dst_vid) AS patent_count,
  MAX(p._seq) AS _seq
FROM vertex_robotics_product_package p
LEFT JOIN vertex_automotive_material_requirement m ON m.package_id = p.package_id
LEFT JOIN vertex_automotive_intermediate_part ip ON ip.package_id = p.package_id
LEFT JOIN vertex_robotics_manufacturing_process pr ON pr.package_id = p.package_id
LEFT JOIN vertex_automotive_responsibility_assignment rp ON rp.package_id = p.package_id
LEFT JOIN edge_automotive_material_supplied_by ms ON ms.material_id = m.material_id
LEFT JOIN edge_automotive_package_references_patent pp ON pp.package_id = p.package_id
WHERE p.asset_kind IN ('autonomous_vehicle', 'vehicle', 'bev', 'hybrid', 'commercial_vehicle')
   OR p.package_profile = 'automotive'
GROUP BY p.package_id, p.product_id, p.revision, p.asset_kind
