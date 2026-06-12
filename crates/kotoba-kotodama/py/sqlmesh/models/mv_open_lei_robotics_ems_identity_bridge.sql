-- Open LEI robotics EMS identity bridge: LEI entity ↔ EMS company ↔ RFQ match cross-link.
MODEL (
  name dev.mv_open_lei_robotics_ems_identity_bridge,
  kind FULL,
  dialect postgres,
  description 'Per LEI entity: matched EMS company, RFQ aggregate matches, and shortlist decision flag.',
  grain [lei_entity_vid, ems_company_id],
  tags [open_lei, robotics_ems, identity_bridge]
);

SELECT
  le.vertex_id AS lei_entity_vid,
  le.lei,
  le.legal_name,
  le.country,
  le.registration_status,
  le.status AS lei_lifecycle_status,
  e.ems_company_id,
  rc.vertex_id AS ems_company_vid,
  rc.display_name AS ems_display_name,
  rc.country_code AS ems_country_code,
  rc.region AS ems_region,
  rc.source AS ems_source,
  rc.risk_level AS ems_risk_level,
  e.match_score AS lei_ems_match_score,
  e.matched_keywords_json,
  e.next_evidence_json,
  COUNT(DISTINCT rfq.edge_id) AS rfq_match_count,
  MAX(rfq.match_score) AS best_rfq_match_score,
  MAX(CASE WHEN rfq.decision = 'shortlist' THEN 1 ELSE 0 END) AS has_shortlist_decision,
  MAX(GREATEST(COALESCE(le._seq, 0), COALESCE(e._seq, 0), COALESCE(rc._seq, 0))) AS _seq
FROM edge_open_lei_entity_ems_candidate e
JOIN vertex_open_lei_entity le ON le.vertex_id = e.src_vid
LEFT JOIN vertex_robotics_ems_company rc
  ON rc.vertex_id = e.dst_vid
  OR rc.company_id = e.ems_company_id
LEFT JOIN edge_robotics_ems_company_matches_rfq rfq
  ON rfq.src_vid = rc.vertex_id
GROUP BY le.vertex_id, le.lei, le.legal_name, le.country, le.registration_status,
         le.status, e.ems_company_id, rc.vertex_id, rc.display_name,
         rc.country_code, rc.region, rc.source, rc.risk_level, e.match_score,
         e.matched_keywords_json, e.next_evidence_json
