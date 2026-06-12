-- Calendar RSVP summary: accept/decline/tentative counts per event.
MODEL (
  name dev.mv_calendar_rsvp_summary,
  kind FULL,
  dialect postgres,
  description 'Per-event total RSVPs and accept/decline/tentative counts with last_seq watermark.',
  grain [event_id],
  tags [calendar, rsvp, event, accept, decline]
);

SELECT
  event_id,
  COUNT(*) AS total_rsvps,
  SUM(CASE WHEN LOWER(COALESCE(response, '')) = 'accept' THEN 1 ELSE 0 END) AS accept_count,
  SUM(CASE WHEN LOWER(COALESCE(response, '')) = 'decline' THEN 1 ELSE 0 END) AS decline_count,
  SUM(CASE WHEN LOWER(COALESCE(response, '')) = 'tentative' THEN 1 ELSE 0 END) AS tentative_count,
  MAX(_seq) AS last_seq
FROM vertex_calendar_rsvp
WHERE event_id IS NOT NULL
GROUP BY event_id
