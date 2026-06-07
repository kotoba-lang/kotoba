-- Attacker device fingerprint timeline: distinct IPs per device for proxy rotation detection.
MODEL (
  name dev.mv_attacker_device_timeline,
  kind FULL,
  dialect postgres,
  description 'Per target_entity_id/device_fingerprint: distinct IP count, hit count, first/last seen, UA details.',
  grain [target_entity_id, device_fingerprint],
  tags [attacker, yabai, device, fingerprint, rotation]
);

SELECT
  target_entity_id,
  device_fingerprint,
  COUNT(DISTINCT accessor_ip) AS distinct_ip_count,
  COUNT(*) AS hit_count,
  MIN(accessed_at) AS first_seen,
  MAX(accessed_at) AS last_seen,
  MAX(ua_browser) AS ua_browser,
  MAX(ua_os) AS ua_os,
  MAX(canvas_hash) AS canvas_hash,
  MAX(webgl_renderer) AS webgl_renderer
FROM vertex_yabai_tracking_hit
WHERE target_entity_id IS NOT NULL AND device_fingerprint IS NOT NULL
GROUP BY target_entity_id, device_fingerprint
