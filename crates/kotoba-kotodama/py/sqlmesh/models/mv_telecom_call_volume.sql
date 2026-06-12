-- Telecom call volume: voice call counts and durations per voltype/codec/status.
MODEL (
  name dev.mv_telecom_call_volume,
  kind FULL,
  dialect postgres,
  description 'Per (session_voltype, codec, status): call count and total duration seconds.',
  grain [session_voltype, codec, status],
  tags [telecom, ims, call_volume]
);

SELECT
  session_voltype,
  codec,
  status,
  COUNT(*) AS call_count,
  SUM(duration_seconds) AS total_duration_seconds
FROM vertex_telecom_voice_call
GROUP BY session_voltype, codec, status
