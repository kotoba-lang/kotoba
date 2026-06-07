-- Robotics manufacturing package readiness: per-package file/process/QA/RFQ rollup.
MODEL (
  name dev.mv_robotics_manufacturing_package_readiness,
  kind FULL,
  dialect postgres,
  description 'Per package: file counts (total/required/present/missing), process/QA/RFQ counts.',
  grain [package_vid],
  tags [robotics, manufacturing, package, readiness]
);

SELECT
  p.vertex_id AS package_vid,
  p.package_id,
  p.product_id,
  p.revision,
  p.asset_kind,
  p.package_profile,
  p.validation_status,
  p.readiness_status,
  COUNT(DISTINCT f.vertex_id) AS file_count,
  COUNT(DISTINCT CASE WHEN f.required THEN f.vertex_id ELSE NULL END) AS required_file_count,
  COUNT(DISTINCT CASE WHEN f.required AND f.present THEN f.vertex_id ELSE NULL END) AS present_required_file_count,
  COUNT(DISTINCT CASE WHEN f.required AND NOT f.present THEN f.vertex_id ELSE NULL END) AS missing_required_file_count,
  COUNT(DISTINCT pr.vertex_id) AS process_count,
  COUNT(DISTINCT qg.vertex_id) AS quality_gate_count,
  COUNT(DISTINCT rfq.vertex_id) AS rfq_count,
  MAX(p._seq) AS _seq
FROM vertex_robotics_product_package p
LEFT JOIN vertex_robotics_product_file f ON f.package_id = p.package_id
LEFT JOIN vertex_robotics_manufacturing_process pr ON pr.package_id = p.package_id
LEFT JOIN vertex_robotics_quality_gate qg ON qg.package_id = p.package_id
LEFT JOIN vertex_robotics_rfq rfq ON rfq.package_id = p.package_id
GROUP BY p.vertex_id, p.package_id, p.product_id, p.revision, p.asset_kind,
         p.package_profile, p.validation_status, p.readiness_status
