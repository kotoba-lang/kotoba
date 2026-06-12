-- Vertex Stripe authorization count: per-actor Stripe authorization count.
MODEL (
  name dev.mv_vertex_stripe_authorization_count,
  kind FULL,
  dialect postgres,
  description 'Per actor_id: Stripe authorization count.',
  grain [actor_id],
  tags [stripe, authorization, count]
);

SELECT
  actor_id,
  COUNT(*)::BIGINT AS cnt
FROM vertex_stripe_authorization
GROUP BY actor_id
