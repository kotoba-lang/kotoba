-- Collector dashboard metric counts: collector runs, DNS observations, blockchain addresses, scan results, archive snapshots.
MODEL (
  name dev.mv_collector_dashboard_counts,
  kind FULL,
  dialect postgres,
  description 'UNION of metric counts from collector_run, dns_observation, blockchain_actor, scan_result tables.',
  grain [metric],
  tags [collector, dashboard, dns, blockchain, scan, archive]
);

SELECT 'collectorRuns'::VARCHAR AS metric, COUNT(*)::BIGINT AS cnt
FROM vertex_collector_run
WHERE repo IS NOT NULL

UNION ALL

SELECT 'dnsObservations'::VARCHAR, COUNT(*)::BIGINT
FROM vertex_dns_observation
WHERE repo IS NOT NULL

UNION ALL

SELECT 'btcAddresses'::VARCHAR, COUNT(*)::BIGINT
FROM vertex_blockchain_actor
WHERE chain = 'btc'

UNION ALL

SELECT 'ethAddresses'::VARCHAR, COUNT(*)::BIGINT
FROM vertex_blockchain_actor
WHERE chain = 'eth'

UNION ALL

SELECT 'scanResults'::VARCHAR, COUNT(*)::BIGINT
FROM vertex_scan_result
WHERE repo IS NOT NULL

UNION ALL

SELECT 'archiveSnapshots'::VARCHAR, COUNT(*)::BIGINT
FROM vertex_blockchain_actor
WHERE repo IS NOT NULL
