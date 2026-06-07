-- Webya sites by status: site count per status.
MODEL (
  name dev.mv_webya_sites_by_status,
  kind FULL,
  dialect postgres,
  description 'Per status: site count from vertex_webya_site.',
  grain [status],
  tags [webya, site, status, count]
);

SELECT
  status,
  COUNT(*) AS site_count
FROM vertex_webya_site
GROUP BY status
