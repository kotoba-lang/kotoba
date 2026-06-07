-- Telecom WLAN RCOI state: WLAN RCOI counts per federation/profile/status.
MODEL (
  name dev.mv_telecom_wlan_rcoi_state,
  kind FULL,
  dialect postgres,
  description 'Per (federation, profile_kind, status): WLAN RCOI count.',
  grain [federation, profile_kind, status],
  tags [telecom, wlan, rcoi]
);

SELECT
  federation,
  profile_kind,
  status,
  COUNT(*) AS rcoi_count
FROM vertex_telecom_wlan_rcoi
GROUP BY federation, profile_kind, status
