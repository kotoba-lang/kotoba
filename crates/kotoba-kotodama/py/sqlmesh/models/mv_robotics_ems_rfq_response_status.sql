-- Robotics EMS RFQ response status: shortlisted/review companies per RFQ package.
MODEL (
  name dev.mv_robotics_ems_rfq_response_status,
  kind FULL,
  dialect postgres,
  description 'Per (rfq_id, package_id, company): match score, decision, missing capabilities, next evidence.',
  grain [rfq_id, package_id, company_id],
  tags [robotics_ems, rfq, shortlist, response]
);

SELECT
  m.rfq_id,
  m.package_id,
  c.company_id,
  c.display_name,
  c.country_code,
  c.region,
  m.match_score,
  m.decision,
  m.missing_capabilities_json,
  m.next_evidence_json,
  MAX(m._seq) AS _seq
FROM edge_robotics_ems_company_matches_rfq m
JOIN vertex_robotics_ems_company c ON c.vertex_id = m.src_vid
WHERE m.decision IN ('shortlist', 'review')
GROUP BY m.rfq_id, m.package_id, c.company_id, c.display_name, c.country_code,
         c.region, m.match_score, m.decision, m.missing_capabilities_json,
         m.next_evidence_json
