-- Site WAT total: aggregate WAT count.
MODEL (
  name dev.mv_site_wat_total,
  kind FULL,
  dialect postgres,
  description 'Total WAT count from vertex_wat.',
  grain [],
  tags [site, wat, total]
);

SELECT COUNT(*)::BIGINT AS cnt
FROM vertex_wat
