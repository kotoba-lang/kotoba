-- Bunken scheme coverage: item counts per bibliographic scheme with enrichment metrics.
MODEL (
  name dev.mv_bunken_scheme_coverage,
  kind FULL,
  dialect postgres,
  description 'Per bibliographic scheme: total items, DID-registered count, and title-enriched count.',
  grain [scheme],
  tags [bunken, bibliographic, scheme, coverage, did]
);

SELECT
  scheme,
  COUNT(*) AS item_count,
  COUNT(*) FILTER (WHERE did_registered) AS did_registered_count,
  COUNT(*) FILTER (WHERE title IS NOT NULL AND title <> '') AS enriched_count
FROM vertex_bunken_bibliographic_item
GROUP BY scheme
