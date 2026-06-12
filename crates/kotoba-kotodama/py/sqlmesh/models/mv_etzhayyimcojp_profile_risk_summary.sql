-- Etzhayyimcojp profile risk summary: aggregate Big5 + risk metrics across all person profiles.
MODEL (
  name dev.mv_etzhayyimcojp_profile_risk_summary,
  kind FULL,
  dialect postgres,
  description 'Aggregate Big5/self-preservation/risk-tolerance/autonomy averages from person profiles.',
  grain [],
  tags [etzhayyimcojp, profile, big5, risk]
);

SELECT
  COUNT(DISTINCT person_did) AS person_count,
  AVG(big5_openness) AS avg_openness,
  AVG(big5_conscientiousness) AS avg_conscientiousness,
  AVG(big5_extraversion) AS avg_extraversion,
  AVG(big5_agreeableness) AS avg_agreeableness,
  AVG(big5_neuroticism) AS avg_neuroticism,
  AVG(self_preservation) AS avg_self_preservation,
  AVG(risk_tolerance) AS avg_risk_tolerance,
  AVG(autonomy_level) AS avg_autonomy
FROM vertex_etzhayyimcojp_person_profile
