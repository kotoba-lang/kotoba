-- Yabai infra hosting rollup: domain counts per hosting provider and ASN.
MODEL (
  name dev.mv_yabai_infra_hosting_rollup,
  kind FULL,
  dialect postgres,
  description 'Per (hosting_provider, asn, asn_country): domain count from latest infra probes.',
  grain [hosting_provider, asn, asn_country],
  tags [yabai, infra, hosting, asn]
);

SELECT
  hosting_provider,
  asn,
  asn_country,
  COUNT(DISTINCT domain) AS domain_count
FROM dev.mv_yabai_infra_latest
GROUP BY hosting_provider, asn, asn_country
