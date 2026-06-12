-- Webya domain SSL pending: domains not yet at active SSL status.
MODEL (
  name dev.mv_webya_domain_ssl_pending,
  kind FULL,
  dialect postgres,
  description 'Domains where ssl_status is not active, with verification details.',
  grain [vertex_id],
  tags [webya, domain, ssl, pending]
);

SELECT
  d.vertex_id,
  d.site_id,
  d.domain,
  d.ssl_status,
  d.ownership_verified,
  d.dns_cname_target,
  d.verification_txt_name,
  d.verification_txt_value,
  d.provisioned_at
FROM vertex_webya_domain d
WHERE d.ssl_status <> 'active'
