-- Open SWIFT pending messages: per-sender SWIFT messages awaiting processing.
MODEL (
  name dev.mv_open_swift_pending_messages,
  kind FULL,
  dialect postgres,
  description 'Per sender_vid: pending SWIFT message count, manual review flag, total amount, latest submission.',
  grain [sender_vid],
  tags [open_swift, pending, payment]
);

SELECT
  sender_vid,
  COUNT(*) AS pending_count,
  BOOL_OR(require_manual_review) AS any_manual_review,
  SUM(amount) AS pending_amount_sum,
  MAX(submitted_at) AS latest_submitted_at
FROM vertex_open_swift_message
WHERE status IN ('submitted', 'pending')
GROUP BY sender_vid
