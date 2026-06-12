-- Gov org count by domain tier: org count rolled up by domain_code + org_tier.
MODEL (
  name dev.mv_gov_org_count_by_domain_tier,
  kind FULL,
  dialect postgres,
  description 'Per (domain_code, org_tier): org count. Includes an __all__ rollup row per domain.',
  grain [domain_code, org_tier],
  tags [gov, org, count, domain, tier]
);

SELECT
  domain_code,
  '__all__'::VARCHAR AS org_tier,
  COUNT(*)::BIGINT AS cnt
FROM vertex_gov_org
WHERE COALESCE(name_en, '') <> ''
GROUP BY domain_code

UNION ALL

SELECT
  domain_code,
  COALESCE(org_tier, '') AS org_tier,
  COUNT(*)::BIGINT AS cnt
FROM vertex_gov_org
WHERE COALESCE(name_en, '') <> ''
GROUP BY domain_code, COALESCE(org_tier, '')
