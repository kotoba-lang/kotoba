-- Maps spatial label counts: spatial entity counts per label and status.
MODEL (
  name dev.mv_maps_spatial_label_counts,
  kind FULL,
  dialect postgres,
  description 'Per (label, status): entity count and latest created_at from vertex_spatial.',
  grain [label, status],
  tags [maps, spatial, label, counts]
);

SELECT
  label,
  status,
  COUNT(*) AS entity_count,
  MAX(created_at) AS latest_created_at
FROM vertex_spatial
GROUP BY label, status
