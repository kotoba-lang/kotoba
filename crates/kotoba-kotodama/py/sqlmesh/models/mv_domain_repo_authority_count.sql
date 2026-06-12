-- Domain coverage: authority record count per (authority_kind, repo).
MODEL (
  name dev.mv_domain_repo_authority_count,
  kind FULL,
  dialect postgres,
  description 'Authority record count per (authority_kind, repo) — feeds mv_domain_coverage_live.',
  grain [authority_kind, repo],
  tags [coverage, domain, authority]
);

SELECT 'sovereign'::text    AS authority_kind, repo, COUNT(*)::bigint AS authority_count FROM vertex_authority_sovereign    GROUP BY repo
UNION ALL
SELECT 'treaty'::text       AS authority_kind, repo, COUNT(*)::bigint AS authority_count FROM vertex_authority_treaty       GROUP BY repo
UNION ALL
SELECT 'religious'::text    AS authority_kind, repo, COUNT(*)::bigint AS authority_count FROM vertex_authority_religious    GROUP BY repo
UNION ALL
SELECT 'customary'::text    AS authority_kind, repo, COUNT(*)::bigint AS authority_count FROM vertex_authority_customary    GROUP BY repo
UNION ALL
SELECT 'community'::text    AS authority_kind, repo, COUNT(*)::bigint AS authority_count FROM vertex_authority_community    GROUP BY repo
UNION ALL
SELECT 'professional'::text AS authority_kind, repo, COUNT(*)::bigint AS authority_count FROM vertex_authority_professional GROUP BY repo
UNION ALL
SELECT 'industry'::text     AS authority_kind, repo, COUNT(*)::bigint AS authority_count FROM vertex_authority_industry     GROUP BY repo
UNION ALL
SELECT 'blockchain'::text   AS authority_kind, repo, COUNT(*)::bigint AS authority_count FROM vertex_authority_blockchain   GROUP BY repo
