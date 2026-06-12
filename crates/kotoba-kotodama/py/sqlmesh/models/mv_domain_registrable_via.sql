-- Domain registrable via: TLD registration availability summary.
MODEL (
  name dev.mv_domain_registrable_via,
  kind FULL,
  dialect postgres,
  description 'Per active TLD: operator, restriction flags, eligibility summary, and registrar count.',
  grain [tld],
  tags [domain, tld, registrar, eligibility, registration]
);

SELECT
  t.tld,
  t.operator,
  t.restricted,
  t.verification_required,
  t.eligibility_summary,
  COUNT(e.edge_id) AS registrar_count
FROM vertex_domain_tld t
LEFT JOIN edge_domain_registrar_supports_tld e ON e.tld = t.tld
WHERE t.status = 'active'
GROUP BY t.tld, t.operator, t.restricted, t.verification_required, t.eligibility_summary
