-- JP fiscal actor relationship degree: outbound relationship counts per actor.
MODEL (
  name dev.mv_jp_fiscal_actor_relationship_degree,
  kind FULL,
  dialect postgres,
  description 'Per (subject_did, relationship_type): outbound count and distinct object count.',
  grain [subject_did, relationship_type],
  tags [jp_fiscal, actor, relationship, degree]
);

SELECT
  subject_did,
  relationship_type,
  COUNT(*) AS outbound_count,
  COUNT(DISTINCT object_did) AS distinct_object_count
FROM edge_jp_fiscal_actor_relationship
GROUP BY subject_did, relationship_type
