-- Hospitality actor coverage: count of actors per kind under hospitality DID prefix.
MODEL (
  name dev.mv_hospitality_actor_coverage,
  kind FULL,
  dialect postgres,
  description 'Per actor kind: count of hospitality actors with did:web:hospitality.etzhayyim.com:actor: prefix.',
  grain [kind],
  tags [hospitality, actor, coverage]
);

SELECT
  split_part(split_part(did, ':actor:', 2), ':', 1) AS kind,
  COUNT(*) AS actor_cnt
FROM vertex_profile
WHERE did LIKE 'did:web:hospitality.etzhayyim.com:actor:%'
GROUP BY split_part(split_part(did, ':actor:', 2), ':', 1)
