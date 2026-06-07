-- Yoro evolution recent: union of 5 evolution event kinds for unified timeline.
MODEL (
  name dev.mv_yoro_evolution_recent,
  kind FULL,
  dialect postgres,
  description 'Union of KojiDiscovery/KyumeiValidation/ShinkaEvolution/HinshitsuAssessment/ShinkaKnowledge for unified actor evolution timeline.',
  grain [label, actorDid, createdAt],
  tags [yoro, evolution, recent, timeline]
);

SELECT 'KojiDiscovery' AS label, actor_did AS "actorDid", actor_name AS "actorName",
  readiness_grade AS "readinessGrade", summary, NULL::TEXT AS "validationScore", NULL::TEXT AS mood,
  NULL::TEXT AS "qualityScore", NULL::TEXT AS grade, NULL::TEXT AS "domainSummary", source, created_at AS "createdAt"
FROM vertex_yoro_koji_discovery
UNION ALL
SELECT 'KyumeiValidation' AS label, actor_did AS "actorDid", actor_name AS "actorName",
  NULL::TEXT AS "readinessGrade", NULL::TEXT AS summary, validation_score AS "validationScore", NULL::TEXT AS mood,
  NULL::TEXT AS "qualityScore", NULL::TEXT AS grade, NULL::TEXT AS "domainSummary", source, created_at AS "createdAt"
FROM vertex_yoro_kyumei_validation
UNION ALL
SELECT 'ShinkaEvolution' AS label, actor_did AS "actorDid", actor_name AS "actorName",
  NULL::TEXT AS "readinessGrade", NULL::TEXT AS summary, NULL::TEXT AS "validationScore", mood,
  NULL::TEXT AS "qualityScore", NULL::TEXT AS grade, NULL::TEXT AS "domainSummary", source, created_at AS "createdAt"
FROM vertex_yoro_shinka_evolution
UNION ALL
SELECT 'HinshitsuAssessment' AS label, actor_did AS "actorDid", actor_name AS "actorName",
  NULL::TEXT AS "readinessGrade", NULL::TEXT AS summary, NULL::TEXT AS "validationScore", NULL::TEXT AS mood,
  quality_score AS "qualityScore", grade, NULL::TEXT AS "domainSummary", source, created_at AS "createdAt"
FROM vertex_yoro_hinshitsu_assessment
UNION ALL
SELECT 'ShinkaKnowledge' AS label, actor_did AS "actorDid", actor_name AS "actorName",
  NULL::TEXT AS "readinessGrade", NULL::TEXT AS summary, NULL::TEXT AS "validationScore", NULL::TEXT AS mood,
  NULL::TEXT AS "qualityScore", NULL::TEXT AS grade, domain_summary AS "domainSummary", source, created_at AS "createdAt"
FROM vertex_yoro_shinka_knowledge
