-- Telecom WLAN venue inventory: WLAN venue counts per group/jurisdiction/OSU/status.
MODEL (
  name dev.mv_telecom_wlan_venue_inventory,
  kind FULL,
  dialect postgres,
  description 'Per (venue_group, jurisdiction, osu_kind, status): WLAN venue count.',
  grain [venue_group, jurisdiction, osu_kind, status],
  tags [telecom, wlan, venue, inventory]
);

SELECT
  venue_group,
  jurisdiction,
  osu_kind,
  status,
  COUNT(*) AS venue_count
FROM vertex_telecom_wlan_venue
GROUP BY venue_group, jurisdiction, osu_kind, status
