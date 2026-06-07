-- Baminiku stream activity: chat, tip, and track counts per stream.
MODEL (
  name dev.mv_baminiku_stream_activity_counts,
  kind FULL,
  dialect postgres,
  description 'Per-stream chat count, tip count, total tips, and track count from baminiku tables.',
  grain [stream_id],
  tags [baminiku, stream, activity, chat, tip, track]
);

SELECT
  s.stream_id,
  s.agent_did,
  s.status,
  s.visibility,
  COUNT(DISTINCT c.vertex_id)::BIGINT AS chat_count,
  COUNT(DISTINCT t.vertex_id)::BIGINT AS tip_count,
  COALESCE(SUM(t.amount), 0) AS tip_amount_total,
  COUNT(DISTINCT tr.vertex_id)::BIGINT AS track_count
FROM vertex_baminiku_stream s
LEFT JOIN vertex_baminiku_chat c ON c.stream_id = s.stream_id
LEFT JOIN vertex_baminiku_tip t ON t.stream_id = s.stream_id
LEFT JOIN vertex_baminiku_track tr ON tr.stream_id = s.stream_id
GROUP BY s.stream_id, s.agent_did, s.status, s.visibility
