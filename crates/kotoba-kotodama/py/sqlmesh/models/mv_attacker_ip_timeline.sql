-- Attacker IP timeline: hit count and geo/proxy flags per target entity and IP.
MODEL (
  name dev.mv_attacker_ip_timeline,
  kind FULL,
  dialect postgres,
  description 'Per target_entity_id/accessor_ip: first/last seen, hit count, geoip, and proxy flags from vertex_yabai_tracking_hit.',
  grain [target_entity_id, accessor_ip],
  tags [attacker, yabai, ip, timeline, geoip, proxy]
);

SELECT
  target_entity_id,
  accessor_ip,
  MIN(accessed_at) AS first_seen,
  MAX(accessed_at) AS last_seen,
  COUNT(*) AS hit_count,
  MAX(geoip_country) AS geoip_country,
  MAX(geoip_asn) AS geoip_asn,
  MAX(geoip_isp) AS geoip_isp,
  BOOL_OR(is_proxy) AS ever_proxy,
  BOOL_OR(is_datacenter) AS ever_datacenter,
  BOOL_OR(is_tor) AS ever_tor
FROM vertex_yabai_tracking_hit
WHERE target_entity_id IS NOT NULL AND accessor_ip IS NOT NULL
GROUP BY target_entity_id, accessor_ip
