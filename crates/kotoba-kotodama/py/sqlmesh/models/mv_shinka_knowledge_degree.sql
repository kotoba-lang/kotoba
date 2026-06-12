-- Shinka knowledge degree: out-degree per actor from edge_shinka_knowledge.
MODEL (
  name dev.mv_shinka_knowledge_degree,
  kind FULL,
  dialect postgres,
  description 'Per actor_did (src_vid): knowledge out-degree count.',
  grain [actor_did],
  tags [shinka, knowledge, degree, actor]
);

SELECT
  src_vid AS actor_did,
  COUNT(*) AS out_degree
FROM edge_shinka_knowledge
GROUP BY src_vid
