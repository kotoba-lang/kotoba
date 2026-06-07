-- Robotics EMS company readiness: per-company capability and certification rollup.
MODEL (
  name dev.mv_robotics_ems_company_readiness,
  kind FULL,
  dialect postgres,
  description 'Per company: capability count, certification count, verified certification count.',
  grain [company_vid],
  tags [robotics_ems, company, readiness]
);

SELECT
  c.vertex_id AS company_vid,
  c.company_id,
  c.display_name,
  c.country_code,
  c.region,
  c.risk_level,
  COUNT(DISTINCT cap.dst_vid) AS capability_count,
  COUNT(DISTINCT cert.dst_vid) AS certification_count,
  COUNT(DISTINCT CASE WHEN cert.verification_status = 'verified' THEN cert.dst_vid ELSE NULL END) AS verified_certification_count,
  MAX(c._seq) AS _seq
FROM vertex_robotics_ems_company c
LEFT JOIN edge_robotics_ems_company_has_capability cap ON cap.src_vid = c.vertex_id
LEFT JOIN edge_robotics_ems_company_has_certification cert ON cert.src_vid = c.vertex_id
GROUP BY c.vertex_id, c.company_id, c.display_name, c.country_code, c.region, c.risk_level
