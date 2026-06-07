-- Vertex Stripe cardholder count: per-actor Stripe cardholder count.
MODEL (
  name dev.mv_vertex_stripe_cardholder_count,
  kind FULL,
  dialect postgres,
  description 'Per actor_id: Stripe cardholder count.',
  grain [actor_id],
  tags [stripe, cardholder, count]
);

SELECT
  actor_id,
  COUNT(*)::BIGINT AS cnt
FROM vertex_stripe_cardholder
GROUP BY actor_id
