-- Robotics supplier RFQ export: per-(package, RFQ) supplier export with folder breakdown.
MODEL (
  name dev.mv_robotics_supplier_rfq_export,
  kind FULL,
  dialect postgres,
  description 'Per (package, RFQ): supplier kind/region, terms, and folder file counts (CAD/PCB/BOM/Assembly/QA/RFQ).',
  grain [package_id, rfq_id],
  tags [robotics, supplier, rfq, export]
);

SELECT
  p.package_id,
  p.product_id,
  p.revision,
  p.asset_kind,
  rfq.rfq_id,
  rfq.supplier_kind,
  rfq.supplier_region,
  rfq.quantity,
  rfq.moq,
  rfq.target_unit_cost,
  rfq.currency,
  rfq.incoterms,
  rfq.lead_time_days,
  rfq.rfq_status,
  SUM(CASE WHEN f.folder = 'CAD' THEN 1 ELSE 0 END) AS cad_file_count,
  SUM(CASE WHEN f.folder = 'PCB' THEN 1 ELSE 0 END) AS pcb_file_count,
  SUM(CASE WHEN f.folder = 'BOM' THEN 1 ELSE 0 END) AS bom_file_count,
  SUM(CASE WHEN f.folder = 'Assembly' THEN 1 ELSE 0 END) AS assembly_file_count,
  SUM(CASE WHEN f.folder = 'QA' THEN 1 ELSE 0 END) AS qa_file_count,
  SUM(CASE WHEN f.folder = 'RFQ' THEN 1 ELSE 0 END) AS rfq_file_count,
  MAX(p._seq) AS _seq
FROM vertex_robotics_product_package p
JOIN vertex_robotics_rfq rfq ON rfq.package_id = p.package_id
LEFT JOIN vertex_robotics_product_file f ON f.package_id = p.package_id
GROUP BY p.package_id, p.product_id, p.revision, p.asset_kind,
         rfq.rfq_id, rfq.supplier_kind, rfq.supplier_region, rfq.quantity,
         rfq.moq, rfq.target_unit_cost, rfq.currency, rfq.incoterms,
         rfq.lead_time_days, rfq.rfq_status
