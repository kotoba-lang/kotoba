-- Wellbecoming proactive message caller counts: per-caller message count.
MODEL (
  name dev.mv_wellbecoming_proactive_message_caller_counts,
  kind FULL,
  dialect postgres,
  description 'Per caller_did: proactive message count and latest indexed_at.',
  grain [caller_did],
  tags [wellbecoming, proactive_message, caller]
);

SELECT
  caller_did,
  COUNT(*) AS message_count,
  MAX(indexed_at) AS latest_indexed_at
FROM vertex_wellbecoming_proactive_message
GROUP BY caller_did
