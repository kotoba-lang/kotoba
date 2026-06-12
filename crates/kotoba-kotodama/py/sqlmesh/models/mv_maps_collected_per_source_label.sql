-- Maps collected per source label: spatial entity counts per source DID and label.
MODEL (
  name dev.mv_maps_collected_per_source_label,
  kind FULL,
  dialect postgres,
  description 'Per (source_did, label): collected_count from vertex_spatial.',
  grain [source_did, label],
  tags [maps, spatial, source, label]
);

SELECT
  source_did,
  label,
  COUNT(*)::BIGINT AS collected_count
FROM vertex_spatial
GROUP BY source_did, label
