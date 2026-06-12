-- Open LEI EMS candidates: LEI entity to EMS company candidate matches.
MODEL (
  name dev.mv_open_lei_ems_candidates,
  kind FULL,
  dialect postgres,
  description 'Per (LEI, EMS company): match score, keywords, evidence, and max _seq.',
  grain [lei, ems_company_id],
  tags [open_lei, ems, candidate, match]
);

SELECT
  e.lei,
  e.legal_name,
  e.country,
  e.registration_status,
  c.ems_company_id,
  c.match_score,
  c.matched_keywords_json,
  c.next_evidence_json,
  MAX(c._seq) AS _seq
FROM edge_open_lei_entity_ems_candidate c
JOIN vertex_open_lei_entity e ON e.vertex_id = c.src_vid
GROUP BY e.lei, e.legal_name, e.country, e.registration_status,
         c.ems_company_id, c.match_score, c.matched_keywords_json,
         c.next_evidence_json
