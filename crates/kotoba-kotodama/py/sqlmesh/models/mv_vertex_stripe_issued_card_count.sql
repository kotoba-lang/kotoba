-- Vertex Stripe issued card count: per-actor Stripe issued card count.
MODEL (
  name dev.mv_vertex_stripe_issued_card_count,
  kind FULL,
  dialect postgres,
  description 'Per actor_id: Stripe issued card count.',
  grain [actor_id],
  tags [stripe, issued_card, count]
);

SELECT
  actor_id,
  COUNT(*)::BIGINT AS cnt
FROM vertex_stripe_issued_card
GROUP BY actor_id
