-- Site page total: aggregate page count.
MODEL (
  name dev.mv_site_page_total,
  kind FULL,
  dialect postgres,
  description 'Total page count from vertex_page.',
  grain [],
  tags [site, page, total]
);

SELECT COUNT(*)::BIGINT AS cnt
FROM vertex_page
