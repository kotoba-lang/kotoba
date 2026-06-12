-- Domain coverage: live DID count per (kind, repo) from dim_domain_coverage_target.
MODEL (
  name dev.mv_domain_repo_did_count,
  kind FULL,
  dialect postgres,
  description 'Live DID count per (kind, repo) — feeds mv_domain_coverage_live.',
  grain [kind, repo],
  tags [coverage, domain, did]
);

SELECT
  t.kind,
  t.repo,
  COUNT(*)::bigint AS did_count
FROM dim_domain_coverage_target t
LEFT JOIN vertex_did d ON d.repo = t.repo
GROUP BY t.kind, t.repo
