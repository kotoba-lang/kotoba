-- Yabai infra latest: most recent probe result per domain (DISTINCT ON rewritten for RisingWave).
MODEL (
  name dev.mv_yabai_infra_latest,
  kind FULL,
  dialect postgres,
  description 'Latest probe result per domain from vertex_yabai_infra_track using GROUP BY + JOIN.',
  grain [domain],
  tags [yabai, infra, probe, latest]
);

SELECT
  t.domain,
  t.entity_id,
  t.probed_at,
  t.resolved_ip,
  t.asn,
  t.asn_org,
  t.hosting_provider,
  t.registrar,
  t.whois_created,
  t.tls_issuer,
  t.tls_not_after,
  t.http_status,
  t.http_server,
  t.probe_status
FROM vertex_yabai_infra_track t
JOIN (
  SELECT domain, MAX(probed_at) AS max_probed_at
  FROM vertex_yabai_infra_track
  WHERE domain IS NOT NULL
  GROUP BY domain
) latest ON t.domain = latest.domain AND t.probed_at = latest.max_probed_at
