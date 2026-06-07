-- Maps collected per source label canonical: same as label MV but with canonicalized source DID.
MODEL (
  name dev.mv_maps_collected_per_source_label_canonical,
  kind FULL,
  dialect postgres,
  description 'Per (canonicalized source_did, label): collected_count via maps_canonicalize_source_did UDF.',
  grain [source_did, label],
  tags [maps, spatial, source, label, canonical]
);

SELECT
  maps_canonicalize_source_did(source_did) AS source_did,
  label,
  COUNT(*)::BIGINT AS collected_count
FROM vertex_spatial
WHERE source_did IS NOT NULL AND label IS NOT NULL
GROUP BY maps_canonicalize_source_did(source_did), label
