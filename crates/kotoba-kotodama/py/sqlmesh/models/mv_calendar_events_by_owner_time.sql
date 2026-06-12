-- Calendar events per organizer and start day.
MODEL (
  name dev.mv_calendar_events_by_owner_time,
  kind FULL,
  dialect postgres,
  description 'Count of calendar events per organizer_did and start_day (YYYY-MM-DD) with last_seq watermark.',
  grain [organizer_did, start_day],
  tags [calendar, event, organizer, daily]
);

SELECT
  organizer_did,
  SUBSTRING(COALESCE(start_time, ''), 1, 10) AS start_day,
  COUNT(*) AS event_count,
  MAX(_seq) AS last_seq
FROM vertex_calendar_event
WHERE organizer_did IS NOT NULL
GROUP BY organizer_did, SUBSTRING(COALESCE(start_time, ''), 1, 10)
