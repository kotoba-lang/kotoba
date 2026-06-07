-- World record per host: per-canonicalized-host repo record count.
MODEL (
  name dev.mv_world_record_per_host,
  kind FULL,
  dialect postgres,
  description 'Per canonicalized app_host: repo record count from vertex_repo_record (did:web:%.etzhayyim.com).',
  grain [app_host],
  tags [world, record, host, coverage]
);

SELECT
  COALESCE(a.canonical_host, raw.app_host) AS app_host,
  SUM(raw.record_count) AS record_count
FROM (
  SELECT
    SPLIT_PART(SPLIT_PART(repo, '.etzhayyim.com', 1), 'did:web:', 2) AS app_host,
    COUNT(*) AS record_count
  FROM vertex_repo_record
  WHERE repo IS NOT NULL AND repo LIKE 'did:web:%.etzhayyim.com%'
  GROUP BY SPLIT_PART(SPLIT_PART(repo, '.etzhayyim.com', 1), 'did:web:', 2)
) raw
LEFT JOIN dim_app_host_alias a ON a.alias_host = raw.app_host
GROUP BY COALESCE(a.canonical_host, raw.app_host)
