-- Proxy rotation alert: devices with >= 3 distinct IPs (from mv_attacker_device_timeline).
MODEL (
  name dev.mv_attacker_rotation_alert,
  kind FULL,
  dialect postgres,
  description 'Devices with >=3 distinct IPs filtered from mv_attacker_device_timeline for proxy rotation detection.',
  grain [target_entity_id, device_fingerprint],
  tags [attacker, yabai, rotation, alert, proxy]
);

SELECT
  target_entity_id,
  device_fingerprint,
  distinct_ip_count,
  hit_count,
  first_seen,
  last_seen
FROM mv_attacker_device_timeline
WHERE distinct_ip_count >= 3
