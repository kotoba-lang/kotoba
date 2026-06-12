-- World DID per host: per-canonicalized-host DID count.
MODEL (
  name dev.mv_world_did_per_host,
  kind FULL,
  dialect postgres,
  description 'Per canonicalized app_host: DID count from vertex_profile (did:web:%.etzhayyim.com).',
  grain [app_host],
  tags [world, did, host, coverage]
);

SELECT
  COALESCE(a.canonical_host, raw.app_host) AS app_host,
  SUM(raw.did_count) AS did_count
FROM (
  SELECT
    SPLIT_PART(SPLIT_PART(did, '.etzhayyim.com', 1), 'did:web:', 2) AS app_host,
    COUNT(DISTINCT did) AS did_count
  FROM vertex_profile
  WHERE did IS NOT NULL AND did LIKE 'did:web:%.etzhayyim.com%'
  GROUP BY SPLIT_PART(SPLIT_PART(did, '.etzhayyim.com', 1), 'did:web:', 2)
) raw
LEFT JOIN dim_app_host_alias a ON a.alias_host = raw.app_host
GROUP BY COALESCE(a.canonical_host, raw.app_host)
