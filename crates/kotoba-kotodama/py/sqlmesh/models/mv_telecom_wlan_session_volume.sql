-- Telecom WLAN session volume: WLAN session counts and durations per venue/EAP/IP/status.
MODEL (
  name dev.mv_telecom_wlan_session_volume,
  kind FULL,
  dialect postgres,
  description 'Per (venue_vid, eap_method, ip_assignment, status): session count and total duration_seconds.',
  grain [venue_vid, eap_method, ip_assignment, status],
  tags [telecom, wlan, session, volume]
);

SELECT
  venue_vid,
  eap_method,
  ip_assignment,
  status,
  COUNT(*) AS session_count,
  SUM(duration_seconds) AS total_duration_seconds
FROM vertex_telecom_wlan_session
GROUP BY venue_vid, eap_method, ip_assignment, status
