-- Site screenshot total: aggregate screenshot count.
MODEL (
  name dev.mv_site_screenshot_total,
  kind FULL,
  dialect postgres,
  description 'Total screenshot count from vertex_screenshot.',
  grain [],
  tags [site, screenshot, total]
);

SELECT COUNT(*)::BIGINT AS cnt
FROM vertex_screenshot
