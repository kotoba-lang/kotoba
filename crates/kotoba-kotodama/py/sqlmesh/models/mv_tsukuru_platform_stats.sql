-- Tsukuru platform stats: global counts for manufacturers, factories, and production orders.
MODEL (
  name dev.mv_tsukuru_platform_stats,
  kind FULL,
  dialect postgres,
  description 'Aggregate: total manufacturer, factory, and production order counts across the platform.',
  grain [],
  tags [tsukuru, platform, stats, manufacturing]
);

SELECT
  (SELECT COUNT(*) FROM vertex_tsukuru_manufacturer) AS total_manufacturers,
  (SELECT COUNT(*) FROM vertex_tsukuru_factory) AS total_factories,
  (SELECT COUNT(*) FROM vertex_tsukuru_production_order) AS total_production_orders
