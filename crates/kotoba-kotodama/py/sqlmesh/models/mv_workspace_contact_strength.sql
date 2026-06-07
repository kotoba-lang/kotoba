-- Workspace contact strength: weighted interaction score between actor pairs.
MODEL (
  name dev.mv_workspace_contact_strength,
  kind FULL,
  dialect postgres,
  description 'Per (actor_a, actor_b): sum of weighted interaction counts as strength_score.',
  grain [actor_a, actor_b],
  tags [workspace, contact, strength, network]
);

WITH weighted_edges AS (
  SELECT src_did AS actor_a, dst_did AS actor_b, 1.0 AS weight
  FROM edge_workspace_message_reply
  UNION ALL
  SELECT actor_did AS actor_a, mentioned_did AS actor_b, 2.0 AS weight
  FROM edge_workspace_mention
  UNION ALL
  SELECT actor_did AS actor_a, reacted_did AS actor_b, 0.5 AS weight
  FROM edge_workspace_reaction
)
SELECT
  actor_a,
  actor_b,
  SUM(weight) AS strength_score,
  COUNT(*) AS interaction_count
FROM weighted_edges
GROUP BY actor_a, actor_b
