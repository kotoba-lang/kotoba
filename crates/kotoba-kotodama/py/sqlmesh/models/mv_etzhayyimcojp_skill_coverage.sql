-- Etzhayyimcojp skill coverage: per-skill headcount, proficiency, and verification metrics.
MODEL (
  name dev.mv_etzhayyimcojp_skill_coverage,
  kind FULL,
  dialect postgres,
  description 'Per skill: headcount, avg/max proficiency, peer-verified count.',
  grain [skill_id],
  tags [etzhayyimcojp, skill, coverage]
);

SELECT
  ps.skill_id,
  s.name,
  s.category,
  COUNT(DISTINCT ps.person_did) AS headcount,
  AVG(ps.proficiency) AS avg_proficiency,
  MAX(ps.proficiency) AS max_proficiency,
  SUM(CASE WHEN ps.peer_verified THEN 1 ELSE 0 END) AS verified_count
FROM vertex_etzhayyimcojp_person_skill ps
LEFT JOIN vertex_etzhayyimcojp_skill s ON s.skill_id = ps.skill_id
GROUP BY ps.skill_id, s.name, s.category
