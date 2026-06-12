-- Oil backbone count: per-(country, segment) entity count across 6 oil supply chain segments.
MODEL (
  name dev.mv_oil_backbone_count,
  kind FULL,
  dialect postgres,
  description 'Per (country_code, segment): actor count across upstream/midstream/refining/trading/shipping/distribution.',
  grain [country_code, segment],
  tags [oil, backbone, supply_chain, count]
);

SELECT country_code, 'upstream'::TEXT AS segment, COUNT(*)::BIGINT AS actual_count
FROM vertex_oil_field
GROUP BY country_code
UNION ALL
SELECT COALESCE(SPLIT_PART(locode, '-', 1), 'ZZ') AS country_code, 'midstream'::TEXT AS segment, COUNT(*)::BIGINT AS actual_count
FROM vertex_oil_terminal
GROUP BY COALESCE(SPLIT_PART(locode, '-', 1), 'ZZ')
UNION ALL
SELECT country_code, 'refining'::TEXT AS segment, COUNT(*)::BIGINT AS actual_count
FROM vertex_refinery
GROUP BY country_code
UNION ALL
SELECT country_code, 'trading'::TEXT AS segment, COUNT(*)::BIGINT AS actual_count
FROM vertex_oil_trade
GROUP BY country_code
UNION ALL
SELECT COALESCE(SPLIT_PART(load_port, '-', 1), 'ZZ') AS country_code, 'shipping'::TEXT AS segment, COUNT(*)::BIGINT AS actual_count
FROM vertex_oil_cargo
GROUP BY COALESCE(SPLIT_PART(load_port, '-', 1), 'ZZ')
UNION ALL
SELECT country_code, 'distribution'::TEXT AS segment, COUNT(*)::BIGINT AS actual_count
FROM vertex_product_terminal
GROUP BY country_code
