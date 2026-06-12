-- Robotics EMS LEI RFQ shortlist: LEI-bridged RFQ shortlist with LEI/EMS metadata.
MODEL (
  name dev.mv_robotics_ems_lei_rfq_shortlist,
  kind FULL,
  dialect postgres,
  description 'Per LEI-bridged shortlist row: LEI, EMS company, RFQ ID/score/decision, missing capabilities.',
  grain [lei, rfq_id, package_id],
  tags [robotics_ems, lei, rfq, shortlist]
);

SELECT
  b.lei,
  b.legal_name,
  b.country,
  b.ems_company_id,
  b.ems_company_vid,
  b.ems_display_name,
  rfq.rfq_id,
  rfq.package_id,
  rfq.match_score AS rfq_match_score,
  rfq.decision,
  rfq.missing_capabilities_json,
  rfq.next_evidence_json,
  b.lei_ems_match_score,
  b.ems_risk_level,
  MAX(GREATEST(COALESCE(b._seq, 0), COALESCE(rfq._seq, 0))) AS _seq
FROM dev.mv_open_lei_robotics_ems_identity_bridge b
JOIN edge_robotics_ems_company_matches_rfq rfq
  ON rfq.src_vid = b.ems_company_vid
WHERE rfq.decision IN ('shortlist', 'review')
GROUP BY b.lei, b.legal_name, b.country, b.ems_company_id, b.ems_company_vid,
         b.ems_display_name, rfq.rfq_id, rfq.package_id, rfq.match_score,
         rfq.decision, rfq.missing_capabilities_json, rfq.next_evidence_json,
         b.lei_ems_match_score, b.ems_risk_level
